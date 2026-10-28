# Copyright (c) 2026 A Simple Block. Part of Auto-Finder.
# Source-available, noncommercial use only. No commercial use and no use by
# Excluded Parties without the author's written permission. Credit required.
# See LICENSE.md and EXCLUDED.md in the project repository.
# SPDX-License-Identifier: LicenseRef-Source-Available-Noncommercial-1.0
import os, sys, re, json, time
import threading
import shutil
import urllib.request, urllib.parse, urllib.error
import concurrent.futures
import datetime
import hashlib
import zipfile
import difflib
import shlex
import calendar
import traceback
import random
import glob
__author__ = "A Simple Block"
__license__ = "LicenseRef-Source-Available-Noncommercial-1.0"
__build__ = "af26-mu62ku"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"  #F4
BOLD = "\033[1m"  #F7
RESET = "\033[0m"

CACHE_TTL_SECONDS = 7 * 24 * 3600
CATEGORY_TTL_SECONDS = 30 * 24 * 3600
HTTP_TIMEOUT = 15
HTTP_RETRIES = 5
USER_AGENT = "mod-finder-script"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "found_mods")
CACHE_PATH = os.path.join(SCRIPT_DIR, ".mod_finder_cache.json")
CF_KEY_PATH = os.path.join(SCRIPT_DIR, "CurseForgeApiKey_DO_NOT_SHARE.txt")
CF_KEY_HEADER = "# НЕ ПЕРЕДАВАТЬ ФАЙЛ в файле ключ curseforge не отправляйте этот файл вместе с модами\n"

DEP_TYPE_LABEL = {
    "required": {"ru": "Обязательные зависимости", "en": "Required dependencies"},
    "optional": {"ru": "Опциональные зависимости", "en": "Optional dependencies"},
    "incompatible": {"ru": "Несовместимо с", "en": "Incompatible with"},
    "embedded": {"ru": "Встроено JARinJAR (не отдельный мод)", "en": "Embedded (not a separate mod)"},
}
CF_RELATION_TYPE = {3: "required", 2: "optional", 5: "incompatible", 1: "embedded", 6: "embedded", 4: "embedded"}  #F5
CF_CLASS_ID_MODS = 6
MR_PROJECT_TYPE_MOD = "mod"


TOP_PAGES = 8   #F2
PAGE_SIZE = 50
ADDON_SEARCH_LIMIT = 30
DESC_DIFF_MIN = 10
HTTP_WORKERS = 8
NAME_PAGES = 2
NAME_SEARCH_LIMIT = 20
NAME_MATCH_DESC = False   #F9

ALL_MODS_PATH = os.path.join(OUTPUT_DIR, "mods.txt")
AI_MODS_PATH = os.path.join(OUTPUT_DIR, "mods_ai.txt") #F10 I HATE IA USE IF THIS IS NOT FOR ROUTINE I mean things like testing aghhhhh gI hope you understand what I mean
STORE_PATH = os.path.join(OUTPUT_DIR, ".mods_store.json")
RUN_LOG_PATH = os.path.join(OUTPUT_DIR, "run_log.txt")
RUN_LOG_TAIL = 10

MR_ENV_CLIENT = ["client_only", "client_only_server_optional", "client_and_server",
                 "client_or_server", "client_or_server_prefers_both", "singleplayer_only"]
MR_ENV_SERVER = ["server_only", "dedicated_server_only", "server_only_client_optional",
                 "client_and_server", "client_or_server", "client_or_server_prefers_both",
                 "client_only_server_optional"]

CF_MODLOADER_NAME = {1: "Forge", 2: "Cauldron", 3: "LiteLoader", 4: "Fabric", 5: "Quilt", 6: "NeoForge"}
MR_LOADER_LABEL = {"fabric": "Fabric", "forge": "Forge", "quilt": "Quilt", "neoforge": "NeoForge",
                    "liteloader": "LiteLoader", "rift": "Rift"}
LOADER_ORDER = ["Forge", "Fabric", "NeoForge", "Quilt", "Cauldron", "LiteLoader"]
assert set(CF_RELATION_TYPE.values()) == set(DEP_TYPE_LABEL), "dependency kinds out of sync (E8322)"
assert all(n in CF_MODLOADER_NAME.values() for n in LOADER_ORDER), "loader table drift (E3534)"

T = {
    "ru": {
        "lang_prompt": "Выберите язык / Choose language [ru/en]: ",
        "banner_title": "  Auto-Modpacker by A Simple Block",
        "banner_note": "  Ищет моды на Modrinth и CurseForge. Команда bulk берёт верх категории и аддоны к найденным модам, всё пишется в found_mods/mods.txt (для чтения) и found_mods/mods_ai.txt (сжатый вариант для нейронки, меньше токенов).",
        "commands": ("Команды: key <ключ> | search <тег|name:название|ссылка ...> | show <N> | save <N> | saveall "
                     "| bulk <тег|name:название|ссылка ...> | addons <slug|modid> | build <ссылка|slug ...> | "
                     "importlink | update | newaddons | help | exit"),
        "key_set": "Ключ CurseForge сохранён рядом со скриптом.",
        "key_usage": "Использование: key <ключ>",
        "no_internet": "Нет интернета, поиск невозможен.",
        "net_mr_down": "Modrinth не отвечает, работа только с CurseForge.",
        "net_cf_down": "CurseForge не отвечает, работа только с Modrinth.",
        "auth_error": "API вернул ошибку авторизации (401/403), ключ CurseForge, не принят.",
        "search_usage": "Использование: search <тег1|ссылка|name:название> [тег2|ссылка|name:название ...] (с пробелом в названии: name:iron_man или \"name:iron man\")",
        "search_header": "=== Результаты поиска: {tags} ===",
        "search_none": "Ничего не найдено ни на Modrinth, ни на CurseForge. Проверьте тег: у Modrinth свои категории (technology, magic, adventure, utility, optimization и т. д.), на CurseForge названия отличаются .",
        "search_cf_skipped": "CurseForge пропускаем: ключа нет (команда key).",
        "url_not_recognized": "Не похоже на ссылку на категорию CurseForge/Modrinth, пропускаю: {url}",
        "no_results_yet": "Сначала выполните search.",
        "bad_index": "Нет такого номера.",
        "show_header": "=== {title} ===",
        "field_source": "Источник",
        "field_link": "Ссылка",
        "field_downloads": "Загрузок",
        "field_categories": "Категории",
        "field_description": "Описание",
        "field_deps_none": "Зависимостей нет.",
        "field_deps_note": "Зависимости по последней версии, у старых могут быть другие.",
        "save_done": "Сохранено: {path}",
        "save_error": "Не удалось сохранить: {err}",
        "saveall_done": "Записей сохранено: {n}",
        "bulk_usage": "Использование: bulk <тег|ссылка|name:название> [тег|ссылка|name:название ...] (с пробелом в названии: name:iron_man или \"name:iron man\")",
        "bulk_header": "=== bulk: {query} ===",
        "bulk_thresholds": "Верх категории: {pages} стр. по {size} (по скачиваниям) плюс аддоны найденных модов, до {addons} кандидатов на мод и платформу, {workers} потоков. Настройки в начале файла: TOP_PAGES, PAGE_SIZE, ADDON_SEARCH_LIMIT, HTTP_WORKERS.",
        "bulk_fetching": "Верх категории: {source} / {tag} ...",
        "bulk_cf_category_not_found": "Категория CurseForge «{tag}» не найдена, пропускаю.",
        "bulk_resolving": "Ищу эти же моды на второй платформе и собираю зависимости ({n})...",
        "bulk_addons": "Ищу аддоны (моды, которым нужны найденные), кандидатов: {n}",
        "bulk_progress": "  проверено {done}/{n}",
        "bulk_saving": "  сохраняю...",
        "bulk_addons_found": "Найдено аддонов: {n}",
        "bulk_interrupted": "Прервано, сохраняю то, что успело собраться.",
        "bulk_done_single": "Готово. В списке {total} записей, новых за запуск {new} (из них аддонов {addons}). Файлы: {path} (для чтения), {ai_path} (для нейронки).",
        "origin_top": "верх категории {src}:{tag}",
        "origin_addon": "аддон к {name} ({dep})",
        "origin_manual": "сохранён вручную",
        "f_desc_mr": "Описание (Modrinth)",
        "f_desc_cf": "Описание (CurseForge)",
        "f_found": "Найден",
        "f_loaders": "Версии/загрузчики",
        "file_header": "Моды Minecraft - собрано mod finder. Записей: {n}. Обновлено: {ts}",
        "addons_usage": "Использование: addons <slug|modid>",
        "addons_target_not_found": "Нет такого мода (slug/modid) ни на Modrinth, ни на CurseForge.",
        "addons_header": "=== Возможные аддоны для {name} (возможно, не все) ===",
        "addons_disclaimer": ("Modrinth/CurseForge не отдают oбратные зависимости, только собственные зависимости "
                              "мода, поэтому спросить у них, кто зависит от мода, нельзя. Кандидатов беру текстовым "
                              "поиcком и у каждого проверяю, есть ли в его зависимостях нужный мод. Так находятся не "
                              "все аддоны: часть в поиск просто не попадает."),
        "addons_checking": "Проверяю кандидатов ({n})...",
        "addons_confirmed": "Подтверждено (зависимость на {name} указана):",
        "addons_none_confirmed": "Ни у одного кандидата нет зависимости на {name}.",
        "help_header": "=== Команды ===",
        "help_key": "Сохраняет ключ CurseForge рядом со скриптом. Без ключa CurseForge в поиcке не участвует.",
        "help_search": "Ищет моды на Modrinth и CurseForge. Аргумент: теги (через И) или ссылка на список категории. Выводит нумерованный список с полным описанием. Поиск по названию: name:hulk (с пробелом: name:iron_man или в кавычках), ищет моды, у кoторых эти слова есть в названии или slug, на oбеих площадках.",
        "help_show": "Полная карточка результата N из последнегo search: описание, ссылка, зависимости и нeсовместимости (по последней версии).",
        "help_save": "Добавляет рeзультат N в oбщий список (found_mods/mods.txt + mods_ai.txt).",
        "help_saveall": "Добавляет в общий список все рeзультаты пoследнего search.",
        "help_bulk": ("Берёт ВЕРХ категории (тег или ссылка вида "
                      "modrinth.com/discover/mods?f=categories:optimization&e=client&s=downloads или "
                      "curseforge.com/minecraft/search?...&categories=performance), потом для каждого мода ищет аддоны "
                      "на oбеих площадках. Запросы идут параллельно, прогресс сохраняется по ходу. Один и тот же мод с "
                      "Modrinth и CurseForge собирается в одну запись. Пишет found_mods/mods.txt и "
                      "found_mods/mods_ai.txt (сжатый, для нейронки). Список копится между запусками: чтобы начать с "
                      "нуля, удалите папку found_mods. Вместо категории можно указать название: name:hulk, тогда "
                      "берутся моды с таким словом в названии или slug (NAME_PAGES страниц на платфoрму), дальше "
                      "аддоны как обычно."),
        "help_addons": "Ищет возможные аддоны для мода (slug на Modrinth или modId/slug на CurseForge), кандидатов прoверяет по зависимостям. Список неполный, подробноcти в самой команде.",
        "name_empty": "После name: пусто, пропускаю.",
        "bulk_fetching_name": "Ищу по названию: {source} / «{q}» ...",
        "origin_name": "поиск по названию {src}:{q}",
        "bulk_collect": "Собираю кандидатов в аддоны по названиям модов ({n})...",
        "help_build": ("Автосборка модпака: build <ссылка|slug> [forge|neoforge|fabric|quilt] [версия ...] [mr=N] "
                       "[cf=N]. Ищет аддоны главного мода на Modrinth и CurseForge по зависимостям (и аддоны аддонов), "
                       "делит на блоки по загрузчику и версии Minecraft, помечает exclusive (мод только на одной "
                       "версии) и 'нет на', необязательные отдельно. mr=N / cf=N не берёт моды, у которых на своeй "
                       "платформе скачиваний меньше N (можно 5k, 1m). Моды с похожим назвaнием, но без зависимости, "
                       "спрашивает вручную. Потом можно сделать модпак: "
                       "found_mods/modpacks/<мод>_<загрузчик>_<версия>/mods с готовыми .jar. Отчёты: "
                       "found_mods/build_<мод>.txt и build_<мод>_ai.txt. Также пакует в .mrpack, один и тот же мод на "
                       "Modrinth и CurseForge ищет по хешу файла."),
        "help_importlink": ("Импорт по ссылкам: importlink [prefer CF|M|auto] [min mr=N cf=N] [версия] [загрузчик]. "
                            "Спрашивает версию Minecraft и загрузчик, потом принимает ссылки Modrinth/CurseForge, по "
                            "одной или спиcком (ссылки можно вставить и прямо в скрипт без команды). Для каждогo мода "
                            "смотрит обе площадки и берёт самый новый файл под версию и загрузчик (1.2 новее 1.1.9, "
                            "1.2.2 новее 1.2, 2 новее 1.2), при равных версиях решает prefer (CF!/M! значит всегда эта "
                            "площадка). min mr=N cf=N пропускает площадку, где у мода меньше N скачиваний (min off "
                            "сбрасывает). Обязательные зависимости скачиваются автоматически (deps off выключает). "
                            "Перед скачиванием спрашивает y/n и папку: новая, готовая или папка скрипта. Внутри режима "
                            "есть команды prefer, min, version, loader, deps, folder, settings, exit. Самый новый файл "
                            "выбирается по номеру версии (беты и альфы тоже), only releases берёт только релизы, only "
                            "off возвращает выбор по номеру."),
        "help_update": "Обновление модов в папке: update [версия] [загрузчик] [prefer ...] [min ...]. Спрашивает папку, версию Minecraft и загрузчик сборки, определяет моды (по списку importlink, SHA1 на Modrinth, отпечатку CurseForge), ищет файлы новее на обеих площадках и спрaшивает, что делать: поставить все cразу, по одному или отменить. Старые файлы перемещаются в _old. only releases обновляет только до релизов.",
        "help_newaddons": ("Новые аддоны к моду за период: newaddons <ссылка|slug> [период] [загрузчик] [версия]. "
                           "Период: 7d, 2w, 3m, 1y или словами (неделя, 2 недели, месяц, 3 мес, 10 дней), без периода "
                           "берётся неделя. Смотрит самые свежие проекты на Modrinth и CurseForge, оставляет те, что "
                           "появились за период и нуждаются в этом моде (напрямую или через другой аддон), показывает "
                           "дату, плoщадки, загрузчики с версиями и ссылки. Отдельно идут 'возможные': название "
                           "похoже, а зависимость не указана. Загрузчик и версия сужают список."),
        "help_slug": ("Slug — это окончание ссылки на мод. Например, для ссылки https://modrinth.com/mod/sodium slug "
                      "будет sodium, для ссылки https://modrinth.com/mod/ferrite-core slug будет ferrite-core. На "
                      "CurseForge slug тоже бeрётся из концa ссылки."),
        "cancelled": "Отменено.",
        "interrupted": "Прервано.",
        "mod_not_found": "Мод не найден (нужна ссылка на мод Modrinth/CurseForge или его slug).",
    },
    "en": {
        "lang_prompt": "Выберите язык / Choose language [ru/en]: ",
        "banner_title": "  Mod Finder - by A Simple Block",
        "banner_note": "  Searches Modrinth and CurseForge, mods only no modpacks. bulk takes the top of a category and addons of the found mods, everything goes to found_mods/mods.txt (to read) and found_mods/mods_ai.txt (compact version for an LLM, fewer tokens).",
        "commands": ("Commands: key <key> | search <tag|name:title|url ...> | show <N> | save <N> | saveall | "
                     "bulk <tag|name:title|url ...> | addons <slug|modid> | build <link|slug ...> | importlink | "
                     "update | newaddons | help | exit"),
        "key_set": "CurseForge key saved next to the script.",
        "key_usage": "Usage: key <key>",
        "no_internet": "No internet, nothing to search with.",
        "net_cf_down": "CurseForge is not answering, using Modrinth only.",
        "net_mr_down": "Modrinth is not answering, using CurseForge only.",
        "auth_error": "API complains about auth (401/403), looks like the CurseForge key was not accepted.",
        "search_usage": "Usage: search <tag1|url|name:title> [tag2|url|name:title ...] (space in a title: name:iron_man or \"name:iron man\")",
        "search_header": "=== Search results: {tags} ===",
        "show_hint": "(show N for the full card)",
        "search_none": "Nothing found on Modrinth or CurseForge. Check the tag, Modrinth has its own categories (technology, magic, adventure, utility, optimization etc), names on CurseForge can be different.",
        "search_cf_skipped": "Skipping CurseForge, no key (key command).",
        "url_not_recognized": "Doesn't look like a CurseForge/Modrinth category link, skipping: {url}",
        "no_results_yet": "Do a search first.",
        "cancelled": "Cancelled.",
        "bad_index": "No result with this number.",
        "show_header": "=== {title} ===",
        "field_link": "Link",
        "field_source": "Source",
        "field_downloads": "Downloads",
        "field_categories": "Categories",
        "field_description": "Description",
        "field_deps_none": "No dependencies.",
        "field_deps_note": "Deps are from the latest version, older ones can have other deps.",
        "save_done": "Saved: {path}",
        "save_error": "Couldn't save: {err}",
        "saveall_done": "Saved entries: {n}",
        "bulk_usage": "Usage: bulk <tag|url|name:title> [tag|url|name:title ...] (space in a title: name:iron_man or \"name:iron man\")",
        "bulk_header": "=== bulk: {query} ===",
        "bulk_thresholds": "Top of category: {pages} page(s) x {size} (by downloads) plus addons of the found mods, up to {addons} candidates per mod and platform, {workers} threads. Settings are at the top of the file: TOP_PAGES, PAGE_SIZE, ADDON_SEARCH_LIMIT, HTTP_WORKERS",
        "bulk_fetching": "Top of category: {source} / {tag} ...",
        "bulk_cf_category_not_found": "No such category on CurseForge: '{tag}', skipping.",
        "bulk_resolving": "Looking for the same mods on the other platform and collecting deps ({n})...",
        "bulk_addons": "Looking for addons (mods that need the found ones), candidates: {n}",
        "bulk_progress": "  checked {done}/{n}",
        "bulk_addons_found": "Addons found: {n}",
        "bulk_interrupted": "Interrupted, saving what got collected.",
        "bulk_done_single": "Done. {total} entries in the list, {new} new this run ({addons} of them addons). Files: {path} (readable), {ai_path} (for LLM).",
        "origin_top": "top of category {src}:{tag}",
        "origin_addon": "addon of {name} ({dep})",
        "origin_manual": "saved manually",
        "file_header": "Minecraft mods - collected by mod finder. Entries: {n}. Updated: {ts}",
        "f_desc_mr": "Description (Modrinth)",
        "f_desc_cf": "Description (CurseForge)",
        "f_found": "Found via",
        "f_loaders": "Loaders/versions",
        "addons_usage": "Usage: addons <slug|modid>",
        "addons_target_not_found": "No mod with this slug/modid on Modrinth or CurseForge.",
        "addons_header": "=== Possible addons for {name} (may be not all) ===",
        "addons_disclaimer": ("You can't ask Modrinth/CurseForge who depеnds on a mod, both give only the mod's own dependencies, not "
                              "reverse ones. So candidates come from a text search and each one is checked for the target mod in its "
                              "dependencies. It won't find evеrything, some addons just don't show up in search."),
        "addons_checking": "Checking candidates ({n})...",
        "addons_confirmed": "Confirmed (lists {name} as a dependency):",
        "addons_none_confirmed": "None of the candidates depends on {name}.",
        "help_header": "=== Commands ===",
        "help_key": "Saves the CurseForge key next to the script. No key mеans no CurseForge in search.",
        "help_search": "Searches Modrinth and CurseForge, argumеnt is tags (AND) or a category listing link. Prints a numbered list with full descriptions. By title: name:hulk (with a space use name:iron_man or quotes), finds mods that have thеse words in title or slug, on both platforms.",
        "help_show": "Full card of result N from the last search: description, link, dependencies and incоmpatibilities (latest version).",
        "help_save": "Adds result N to the сommon list (found_mods/mods.txt + mods_ai.txt).",
        "help_saveall": "Adds all results of the last search to the cоmmon list.",
        "help_addons": "Looks for possible addons of a mod (Modrinth slug or CurseForge modId/slug), candidates are checked by dependencies. List is not completе, see the note in the cоmmand itself.",
        "help_bulk": ("Takes the TOP of a category (tag or a link like modrinth.com/discover/mods?f=categories:optimization&e=client&s=downloads "
                      "or curseforge.com/minecraft/search?...&categories=performance), then lоoks for addons of every mod on both "
                      "platforms. Requests run in parallel, progress is saved as it goes. Same mod from Modrinth and CurseForge bеcomes one "
                      "entry. Writes found_mods/mods.txt and found_mods/mods_ai.txt (compact, for an LLM). The list grows between runs, "
                      "delete found_mods to start from zero. Instead of a category you can give a title: name:hulk, then it takes mods with "
                      "that word in title/slug (NAME_PAGES pages per platform), addons after that as usual."),
        "bulk_fetching_name": "Searching by title: {source} / '{q}' ...",
        "origin_name": "title search {src}:{q}",
        "bulk_collect": "Collecting addon candidates by mod names ({n})...",
        "name_empty": "Nothing after name:, skipping.",
        "help_build": ("Modpack builder: build <link|slug> [forge|neoforge|fabric|quilt] [version ...] [mr=N] [cf=N]. Finds addons of the main "
                       "mod on Modrinth and CurseForge by dependencies (and addons of addons), cuts them into loader + Minecraft version "
                       "blocks, mаrks exclusive (mod only on one version) and 'missing on', optional ones go separately. mr=N / cf=N skips "
                       "mods that have fewer than N downloads on their platform (5k, 1m work). Mods with a similar name but no dependency "
                       "are asked manually. Then you can make a modpack: found_mods/modpacks/<mod>_<loader>_<version>/mods with ready .jar "
                       "files. Reports are found_mods/build_<mod>.txt and build_<mod>_ai.txt. Also packs .mrpack, the same mod on Modrinth "
                       "and CurseForge is matсhed by file hash."),
        "help_importlink": ("Import by links: importlink [prefer CF|M|auto] [min mr=N cf=N] [version] [loader]. Asks Minecraft version and loader, "
                            "then takes Modrinth/CurseForge links, one by one or a list (you can also just drop links into the script without "
                            "the command). For every mod it looks at both platforms and takes the newest file for the version and loader (1.2 "
                            "is newer than 1.1.9, 1.2.2 than 1.2, 2 than 1.2), with equal versions prefer decides (CF!/M! means always this "
                            "platform). min mr=N cf=N ignоres a platform where the mod has fewer than N downloads (min off resets). Required "
                            "dependencies are downloaded too (deps off turns it off). Before downloading it asks y/n and the folder: new, "
                            "existing or the script folder. Commands insidе the mode: prefer, min, version, loader, deps, folder, settings, "
                            "exit. Newest file is picked by version number (betas and alphas too), only releases takes releases only, "
                            "only off goes back to by number."),
        "help_update": "Update mods in a folder: update [version] [loader] [prefer ...] [min ...]. Asks the folder, Minecraft version and loader of the build, identifies mods (importlink list, SHA1 on Modrinth, CurseForge fingerprint), lоoks for nеwer files on both platforms and asks what to do: install all at once, one by one, or cancel. Old files go to _old. only releases updates to releases only.",
        "help_newaddons": ("New addons of a mod for a period: newaddons <link|slug> [period] [loader] [version]. Period is 7d, 2w, 3m, 1y or "
                           "words (week, 2 weeks, month, 3 months, 10 days), no period means a week. Looks at the newest projects on Modrinth "
                           "and CurseForge, keeps the ones created in that period that need this mod (directly or through another addon), "
                           "shows date, plаtforms, loaders with versions and links. 'Possible' ones go sеparately, that is similar name but "
                           "no dependency declared. Loader and version narrow the list."),
        "help_slug": ("Slug is the end of a mod's link. For еxample, for the link https://modrinth.com/mod/sodium the "
                      "slug is sоdium, for the link https://modrinth.com/mod/ferrite-core the slug is ferrite-core. On "
                      "CurseForge the slug is also taken from the end of the link."),
        "interrupted": "Interrupted.",
        "mod_not_found": "Mod not found (give a Modrinth/CurseForge mod link or its slug).",
    },
}
assert {"ru", "en"} <= set(T), "locale table missing (E3176)"


LANG = "ru"

def _t(ru, en):
    return ru if LANG == "ru" else en

try:
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        CACHE = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    CACHE = {}

def save_cache():
    #F11
    now = time.time()
    cutoff = max(CACHE_TTL_SECONDS, CATEGORY_TTL_SECONDS)
    fresh = {k: v for k, v in CACHE.items() if isinstance(v, dict) and now - v.get("ts", 0) <= cutoff}
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(fresh, f, ensure_ascii=False)
    except OSError:
        pass

#F68

def dump_json(obj, name="dump.json"):
    with open(os.path.join(SCRIPT_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

def cache_get(key, ttl=None):
    entry = CACHE.get(key)
    if not isinstance(entry, dict) or "ts" not in entry:
        return "MISS"
    if time.time() - entry['ts'] > (ttl if ttl is not None else CACHE_TTL_SECONDS):
        return "MISS"
    return entry.get('v')


def cache_set(key, value):
    CACHE[key] = {'v': value, 'ts': time.time()}

def say(line=""):
    print(line)

#F12
_LAST_REQ = {}
_HTTP_LOCK = threading.Lock()
_AUTH_WARNED = set()


def _note_auth_error(host):
    if host in _AUTH_WARNED:
        return
    _AUTH_WARNED.add(host)
    say(f"{YELLOW}[{host}] {T[LANG]['auth_error']}{RESET}")

def http_get_json(url, headers=None):
    host = urllib.parse.urlparse(url).netloc
    gap = 0.22 if "modrinth" in host else 0.08  #F13
    for attempt in range(5):
        if _CANCEL.is_set():
            return None
        with _HTTP_LOCK:
            wait = gap - (time.time() - _LAST_REQ.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            _LAST_REQ[host] = time.time()
        try:
            req = urllib.request.Request(url, headers=headers or {'User-Agent': "mod-finder-script"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                _note_auth_error(host)
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                try:
                    delay = float(e.headers.get('Retry-After') or e.headers.get('X-Ratelimit-Reset') or 0)
                except (TypeError, ValueError, AttributeError):
                    delay = 0
                _CANCEL.wait(min(max(delay, 2 ** attempt), 65))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            return None
    return None

def _ping(url):
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False

def check_internet():
    ok_mr = _ping("https://api.modrinth.com/v2")
    ok_cf = _ping("https://api.curseforge.com/v1")
    if not ok_mr and not ok_cf:
        return False
    if ok_mr and not ok_cf:
        say(YELLOW + T[LANG]['net_cf_down'] + RESET)
    if ok_cf and not ok_mr:
        say(f"{YELLOW}{T[LANG]['net_mr_down']}{RESET}")
    return True

_CANCEL = threading.Event()  #F3

def _parallel_map(fn, items, workers=HTTP_WORKERS):  #F70
    items = list(items)
    if not items:
        return

    def _run(it):
        if _CANCEL.is_set():
            return None
        return fn(it)

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(items)))
    try:
        futs = [pool.submit(_run, it) for it in items]
        for fut in concurrent.futures.as_completed(futs):
            try:
                fut.result()
            except Exception:
                pass
    except BaseException:
        _CANCEL.set()
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)

#F14

CF_SORT_FIELD = {"featured": 1, "relevancy": 1, "relevance": 1, "popularity": 2, "last updated": 3,
                 "lastupdated": 3, "latest update": 3, "updated": 3, "name": 4, "a-z": 4, "author": 5,
                 "total downloads": 6, "totaldownloads": 6, "downloads": 6, "category": 7, "game version": 8,
                 "gameversion": 8, "creation date": 11, "created": 11, "released date": 11, "releaseddate": 11,
                 "rating": 12}
assert CF_SORT_FIELD["downloads"] == 6, "sort field map changed (E6323)"

def cf_sort_from_url(raw):
    key = re.sub(r"[\s_+]+", " ", (raw or "").strip().lower())
    return CF_SORT_FIELD.get(key, 6)

def parse_listing_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    host = parsed.netloc.lower()
    qs = urllib.parse.parse_qs(parsed.query)
    if "curseforge.com" in host:
        tags = []
        for val in (qs.get('categories') or qs.get('category') or []):
            tags.extend(p.strip() for p in val.split(",") if p.strip())
        if not tags:
            return None
        return {'source': "curseforge", 'tags': tags, 'loaders': [], 'versions': [], 'env': "", 'sort': "downloads",
                'cf_sort': cf_sort_from_url((qs.get('sortBy') or qs.get('sort') or [""])[0])}
    if "modrinth.com" in host:
        def cats(key):
            out = []
            for val in qs.get(key, []):
                for part in val.split(","):
                    part = part.strip()
                    if part.lower().startswith("categories:"):
                        out.append(part.split(":", 1)[1].strip().lower())
            return out
        tags, loaders = cats("f"), cats("g")
        versions = [v.strip() for val in qs.get('v', []) for v in val.split(",") if v.strip()]
        if not tags and not loaders:
            return None
        return {'source': "modrinth", 'tags': tags, 'loaders': loaders, 'versions': versions,
                'env': (qs.get('e') or [""])[0].lower(), 'sort': (qs.get('s') or ["downloads"])[0].lower()}
    return None


def is_url(text):
    return text.startswith("http://") or text.startswith("https://")

NAME_PREFIXES = ("name:", "n:", "название:") #Ftemp1


def parse_name_arg(a):
    low = a.lower()
    for pre in NAME_PREFIXES:
        if low.startswith(pre):
            return _ws(re.sub(r"[_+]+", " ", a[len(pre):]))
    return None

def _name_match(query, *parts):
    words = [w for w in (_blob(x) for x in re.split(r"[\W_]+", query or "")) if w]
    if not words:
        return False
    blob = _blob(*parts)
    return all(w in blob for w in words)

def mr_name_ok(query, h):
    return _name_match(query, h.get("title"), h.get("slug"), h.get("description") if NAME_MATCH_DESC else "")

def cf_name_ok(query, h):
    return _name_match(query, h.get("name"), h.get("slug"), h.get("summary") if NAME_MATCH_DESC else "")

#F15

def cf_only_mods(items):
    out = []
    for h in items or []:
        cid = h.get("classId")
        if cid is None or cid == CF_CLASS_ID_MODS:
            out.append(h)
    return out

def mr_only_mods(hits):
    out = []
    for h in hits or []:
        pt = h.get("project_type")
        if pt == None or pt == MR_PROJECT_TYPE_MOD:
            out.append(h)
    return out

#F16

def modrinth_search(tags, limit=10):
    cache_key = "mr_search_v3f:{}".format(','.join(sorted(t.lower() for t in tags)))
    cached = cache_get(cache_key)
    if cached != "MISS":
        return mr_only_mods(cached)
    facets = [["project_type:mod"]] + [[f"categories:{t.lower()}"] for t in tags]
    url = f"https://api.modrinth.com/v2/search?query=&facets={urllib.parse.quote(json.dumps(facets))}&limit={limit}"
    data = http_get_json(url)
    hits = data.get("hits", []) if data else []
    if data is not None:
        cache_set(cache_key, hits)
    return mr_only_mods(hits)


def modrinth_search_text(query, limit=10):
    cache_key = "mr_text_v3s:{}:{}".format(limit, query.lower())
    cached = cache_get(cache_key)
    if cached != "MISS":
        return mr_only_mods(cached)
    url = (f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}"
           f"&facets={urllib.parse.quote(json.dumps([['project_type:mod']]))}&limit={limit}")
    data = http_get_json(url)
    hits = data.get("hits", []) if data else []
    if data is not None:
        cache_set(cache_key, hits)
    return mr_only_mods(hits)


def modrinth_project(project_id_or_slug):
    cache_key = f"mr_proj_v1n:{project_id_or_slug}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    data = http_get_json("https://api.modrinth.com/v2/project/{}".format(project_id_or_slug))
    if data is not None:
        cache_set(cache_key, data)
    return data

def _mr_fetch_version_data(project_id_or_slug):
    data = http_get_json(f"https://api.modrinth.com/v2/project/{project_id_or_slug}/version")
    if not isinstance(data, list):
        return None
    ordered = sorted((v for v in data if isinstance(v, dict)),
                     key=lambda v: v.get("date_published") or "", reverse=True)
    deps = []
    if ordered:
        for dep in ordered[0].get("dependencies", []) or []:
            deps.append([dep.get("dependency_type"), dep.get("project_id"), dep.get("file_name")])
    loaders = {}
    for v in ordered:
        gvs = v.get("game_versions") or []
        for raw in v.get("loaders") or []:
            loaders.setdefault(_loader_label(raw), set()).update(gvs)
    loaders = {k: sorted(s, key=_ver_key) for k, s in loaders.items()}
    cache_set("mr_deps_v1v:{}".format(project_id_or_slug), deps)
    cache_set("mr_loadver_v1t:{}".format(project_id_or_slug), loaders)
    return deps, loaders

def modrinth_latest_version_deps(project_id_or_slug):
    cache_key = f"mr_deps_v1v:{project_id_or_slug}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    res = _mr_fetch_version_data(project_id_or_slug)
    return res[0] if res else []



def modrinth_loader_versions(project_id_or_slug):
    if not project_id_or_slug:
        return {}
    cache_key = f"mr_loadver_v1t:{project_id_or_slug}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    res = _mr_fetch_version_data(project_id_or_slug)
    return res[1] if res else {}


def modrinth_name_for(project_id):
    if not project_id:
        return project_id
    p = modrinth_project(project_id)
    if p:
        return p.get('title', project_id)
    return project_id

def card_from_mr_project(p):
    slug = p.get("slug")
    return {"source": "Modrinth", "id": p.get("id"), "slug": slug, "title": p.get("title", "?"),
            "description": p.get("description", ""), "downloads": p.get("downloads", 0),
            "categories": p.get("categories", []) or [],
            "link": "https://modrinth.com/mod/{}".format(slug or p.get('id'))}



def _mr_pages(facets, index, query="", pages=None):
    hits = []
    for p in range(pages or TOP_PAGES):
        url = (f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&index={index}"
               f"&facets={urllib.parse.quote(json.dumps(facets))}&limit={PAGE_SIZE}&offset={p * PAGE_SIZE}")
        data = http_get_json(url)
        if data is None:
            return hits, ("fail_first" if p == 0 else "fail_later")
        page = data.get("hits", [])
        hits.extend(page)
        if len(page) < PAGE_SIZE:
            break
    return hits, "ok"

def modrinth_top(task):
    index = task.get("sort") if task.get("sort") in ("relevance", "downloads", "follows", "newest", "updated") else "downloads"
    query = (task.get("query") or "").strip()   #F17
    pages = NAME_PAGES if query else TOP_PAGES
    base = [["project_type:mod"]] + [[f"categories:{t.lower()}"] for t in task["tags"]]
    if task.get("loaders"):
        base.append([f"categories:{x.lower()}" for x in task["loaders"]])
    if task.get("versions"):
        base.append([f"versions:{v}" for v in task["versions"]])
    env_vals = MR_ENV_CLIENT if task.get("env") == "client" else MR_ENV_SERVER if task.get("env") == "server" else None
    facets = base + ([[f"environment:{v}" for v in env_vals]] if env_vals else [])
    if query:
        cache_key = f"mr_topq_v1r:{query.lower()}:{json.dumps(facets)}:{index}:{pages}:{PAGE_SIZE}"
    else:
        cache_key = f"mr_top_v2p:{json.dumps(facets)}:{index}:{TOP_PAGES}:{PAGE_SIZE}"

    def _done(hits):
        hits = mr_only_mods(hits)
        return [h for h in hits if mr_name_ok(query, h)] if query else hits

    cached = cache_get(cache_key)


    if cached != "MISS":
        return _done(cached)
    hits, status = _mr_pages(facets, index, query, pages)
    if status == "fail_first" and env_vals:
        hits, status = _mr_pages(base, index, query, pages)
        hits = [h for h in hits if not h.get("environment") or set(env_vals) & set(h["environment"])]
    if status == "ok":
        cache_set(cache_key, hits)
    return _done(hits)

#F18

def cf_headers(api_key):
    return {"x-api-key": api_key, "Accept": "application/json"}


def cf_search(query, api_key, category_id=None, limit=10):
    cache_key = f"cf_search_v4w:{limit}:{query.lower()}:{category_id}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cf_only_mods(cached)
    url = (f"https://api.curseforge.com/v1/mods/search?gameId=432&classId={CF_CLASS_ID_MODS}"
           f"&searchFilter={urllib.parse.quote(query)}&pageSize={limit}")
    if category_id:
        url += "&categoryId={}".format(category_id)
    data = http_get_json(url, headers=cf_headers(api_key))
    items = data.get("data", []) if data else []
    if data is not None:
        cache_set(cache_key, items)
    return cf_only_mods(items)

#F3_2

def cf_top(category_id, api_key, sort_field=6):
    cache_key = f"cf_top_v3j:{category_id}:{sort_field}:{TOP_PAGES}:{PAGE_SIZE}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cf_only_mods(cached)
    order = "asc" if sort_field in (4, 5) else "desc"
    items, ok = [], True
    for p in range(TOP_PAGES):
        url = (f"https://api.curseforge.com/v1/mods/search?gameId=432&classId={CF_CLASS_ID_MODS}"
               f"&categoryId={category_id}&pageSize={PAGE_SIZE}&index={p * PAGE_SIZE}"
               f"&sortField={sort_field}&sortOrder={order}")
        data = http_get_json(url, headers=cf_headers(api_key))
        if data is None:
            ok = False
            break
        page = data.get('data', [])
        items.extend(page)
        if len(page) < PAGE_SIZE:
            break
    if ok:
        cache_set(cache_key, items)
    return cf_only_mods(items)

def cf_name_top(query, api_key, pages=None):
    t0 = time.time()
    pages = pages or NAME_PAGES
    cache_key = f"cf_nametop_v1a:{query.lower()}:{pages}:{PAGE_SIZE}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return [h for h in cf_only_mods(cached) if cf_name_ok(query, h)]
    items, ok = [], True
    for p in range(pages):
        url = (f"https://api.curseforge.com/v1/mods/search?gameId=432&classId={CF_CLASS_ID_MODS}"
               f"&searchFilter={urllib.parse.quote(query)}&pageSize={PAGE_SIZE}&index={p * PAGE_SIZE}"
               f"&sortField=2&sortOrder=desc")
        data = http_get_json(url, headers=cf_headers(api_key))
        if data is None:
            ok = False
            break
        page = data.get("data", [])
        items.extend(page)
        if len(page) < PAGE_SIZE:
            break
    if ok:
        cache_set(cache_key, items)
    return [h for h in cf_only_mods(items) if cf_name_ok(query, h)]


def cf_categories(api_key):
    cache_key = f"cf_categories_v2a:{CF_CLASS_ID_MODS}"
    cached = cache_get(cache_key, ttl=CATEGORY_TTL_SECONDS)
    if cached != "MISS":
        return cached
    data = http_get_json(
        "https://api.curseforge.com/v1/categories?gameId=432&classId={}".format(CF_CLASS_ID_MODS),
        headers=cf_headers(api_key),
    )
    items = data.get("data", []) if data else []
    if data is not None:
        cache_set(cache_key, items)
    return items

def cf_category_id_for_tag(tag, api_key):
    #F19
    want = re.sub(r"[\W_]+", "", (tag or "").casefold())
    for c in cf_categories(api_key):
        for field in ("slug", "name"):
            if want and re.sub(r"[\W_]+", "", (c.get(field) or "").casefold()) == want:
                return c.get('id')
    return None


def cf_mod_by_slug(slug, api_key):
    cache_key = f"cf_slug_v3b:{slug.lower()}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    url = (f"https://api.curseforge.com/v1/mods/search?gameId=432&classId={CF_CLASS_ID_MODS}"
           f"&slug={urllib.parse.quote(slug)}")
    data = http_get_json(url, headers=cf_headers(api_key))
    items = cf_only_mods(data.get("data", []) if data else [])
    result = items[0] if items else None
    if data is not None:
        cache_set(cache_key, result)
    return result


def cf_mod_by_id(mod_id, api_key):
    cache_key = f"cf_mod_v1z:{mod_id}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    data = http_get_json(f"https://api.curseforge.com/v1/mods/{mod_id}", headers=cf_headers(api_key))
    result = data.get("data") if data else None
    if data is not None:
        cache_set(cache_key, result)
    return result


def cf_latest_file_deps(mod_id, api_key):
    cache_key = f"cf_deps_v1t:{mod_id}"
    cached = cache_get(cache_key)
    if cached != "MISS":
        return cached
    data = http_get_json(f"https://api.curseforge.com/v1/mods/{mod_id}/files?pageSize=1", headers=cf_headers(api_key))
    result = []
    files = data.get('data') if data else None
    if files:
        for dep in files[0].get('dependencies', []) or []:
            kind = CF_RELATION_TYPE.get(dep.get('relationType'), "embedded")
            result.append((kind, dep.get('modId')))
    if data is not None:
        cache_set(cache_key, result)
    return result

def cf_loader_versions(mod_id, api_key):
    skipped = 0
    if not api_key:
        return {}
    m = cf_mod_by_id(mod_id, api_key)
    if not m:
        return {}
    out = {}
    for idx in m.get("latestFilesIndexes") or []:
        loader = CF_MODLOADER_NAME.get(idx.get("modLoader"))
        gv = idx.get("gameVersion")
        if not loader or not gv:
            continue
        out.setdefault(loader, set()).add(gv)
    return {k: sorted(v, key=_ver_key) for k, v in out.items()}


def cf_name_for(mod_id, api_key):
    if not mod_id:
        return str(mod_id)
    m = cf_mod_by_id(mod_id, api_key)
    if m:
        return m.get("name", str(mod_id))
    return str(mod_id)

#F20
def normalize_modrinth_hit(hit):
    return {
        "source": "Modrinth",
        "id": hit.get("project_id") or hit.get("slug"),
        "slug": hit.get("slug"),
        "title": hit.get("title", "?"),
        "description": hit.get("description", ""),
        "downloads": hit.get("downloads", 0),
        "categories": hit.get("categories", []) or hit.get("display_categories", []) or [],
        "link": f"https://modrinth.com/mod/{hit.get('slug', hit.get('project_id'))}",
    }



def normalize_cf_hit(hit):
    links = hit.get('links') or {}
    return {
        'source': "CurseForge",
        'id': hit.get('id'),
        'slug': hit.get('slug'),
        'title': hit.get('name', "?"),
        'description': hit.get('summary', ""),
        'downloads': hit.get('downloadCount', 0),
        'categories': [c.get('name') for c in (hit.get('categories') or [])],
        'link': links.get('websiteUrl') or f"https://www.curseforge.com/minecraft/mc-mods/{hit.get('slug')}", #Ftemp5
    }

def fetch_deps_for(card, api_key):
    result = {"required": [], "optional": [], "incompatible": [], "embedded": []}
    if card["source"] == "Modrinth":
        for dep_type, proj_id, file_name in modrinth_latest_version_deps(card["id"]):
            if dep_type not in result:
                continue
            name = modrinth_name_for(proj_id) if proj_id else (file_name or "?")
            result[dep_type].append(name)
    else:
        if not api_key:
            return result
        for kind, dep_id in cf_latest_file_deps(card["id"], api_key):
            name = cf_name_for(dep_id, api_key)
            result[kind].append(name)
    return result

#F21

def _ws(s):
    return re.sub(r"\s+", " ", s or "").strip()

def norm_title(s):
    s = re.sub(r"[\(\[].*?[\)\]]", " ", (s or "").casefold())
    return re.sub(r"[\W_]+", "", s)


def _blob(*parts):
    return re.sub(r"[\W_]+", "", " ".join(p or "" for p in parts).casefold())

def _titles_similar(a, b):
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return False
    return na == nb or difflib.SequenceMatcher(None, na, nb).ratio() >= 0.85

def edit_distance_capped(a, b, cap):
    if a == b:
        return 0
    if abs(len(a) - len(b)) >= cap:
        return cap
    if len(a) < len(b):
        a, b = b, a
    prev = [min(j, cap) for j in range(len(b) + 1)]
    for i, ca in enumerate(a, 1):
        cur = [cap] * (len(b) + 1)
        cur[0] = min(i, cap)
        for j in range(max(1, i - cap), min(len(b), i + cap) + 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != b[j - 1]))
            cur[j] = v if v < cap else cap
        prev = cur
        if min(cur) >= cap:
            return cap
    return min(prev[len(b)], cap)

def descriptions_differ(a, b):
    a, b = _ws(a).casefold(), _ws(b).casefold()
    return edit_distance_capped(a, b, DESC_DIFF_MIN) >= DESC_DIFF_MIN


def _ver_key(v):
    parts = re.findall(r"\d+", v or "")
    if parts:
        return (0, tuple(int(p) for p in parts))
    return (1, v or "")

def _loader_label(raw):
    key = (raw or "").strip().lower()
    return MR_LOADER_LABEL.get(key, key.capitalize() if key else "?")

#F22

_STORE = None
_REDIRECT = {}  #F6
_DEP_KINDS = ("required", "optional", "incompatible", "embedded")
_STORE_LOCK = threading.RLock()


def _ent_title(e):
    return (e.get("mr") or e.get("cf") or {}).get("title", "?")


def _store_load():
    global _STORE
    if _STORE is not None:
        return _STORE
    _STORE = []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _STORE = [e for e in data if isinstance(e, dict) and (e.get("mr") or e.get("cf"))]
    except (OSError, ValueError):
        pass
    for e in _STORE:
        e.setdefault("deps", {})
        for k in _DEP_KINDS:
            e["deps"].setdefault(k, [])
        e.setdefault("origins", [])
        e.setdefault("deps_done", [])
        e.setdefault("loaders", {})
        e.setdefault("loaders_done", [])
        e["nt"] = norm_title(_ent_title(e))
    return _STORE

def _store_find(card):
    store = _store_load()
    side = "mr" if card["source"] == "Modrinth" else "cf"
    for e in store:
        cur = e.get(side)
        if cur and cur.get("id") == card.get("id"):
            return e
    nt = norm_title(card.get("title"))
    slug = (card.get("slug") or "").lower()
    for e in store:
        if e.get(side):
            continue
        base = e.get("mr") or e.get("cf")
        same_slug = bool(slug) and slug == (base.get("slug") or "").lower()
        if (same_slug or (nt and nt == e.get("nt"))) and _titles_similar(base.get("title"), card.get("title")):
            return e
    return None

def _merge_deps(ent, deps):
    for k in _DEP_KINDS:
        for name in (deps or {}).get(k, []) or []:
            if name and name not in ent['deps'][k]:
                ent['deps'][k].append(name)


def _merge_loaders(ent, loaders):
    bucket = ent.setdefault("loaders", {})
    for name, vers in (loaders or {}).items():
        cur = set(bucket.get(name, []))
        cur.update(vers)
        bucket[name] = sorted(cur, key=_ver_key)

def store_add(card, deps=None, origin=None):
    with _STORE_LOCK:
        store = _store_load()
        ent = _store_find(card)
        side = "mr" if card['source'] == "Modrinth" else "cf"
        if ent is None:
            ent = {'mr': None, 'cf': None, 'deps': {k: [] for k in _DEP_KINDS}, 'origins': [],
                   'deps_done': [], 'loaders': {}, 'loaders_done': [], 'nt': norm_title(card.get('title'))}
            store.append(ent)
        if not ent.get(side):
            ent[side] = card
        _merge_deps(ent, deps)
        if origin and origin not in ent['origins']:
            ent['origins'].append(origin)
        return ent

def _store_merge(keep, drop):
    for side in ("mr", "cf"):
        if not keep.get(side) and drop.get(side):
            keep[side] = drop[side]
    _merge_deps(keep, drop.get("deps"))
    _merge_loaders(keep, drop.get("loaders"))
    for o in drop.get("origins", []):
        if o not in keep["origins"]:
            keep["origins"].append(o)
    for s in drop.get("deps_done", []):
        if s not in keep["deps_done"]:
            keep["deps_done"].append(s)
    for s in drop.get("loaders_done", []):
        if s not in keep.setdefault("loaders_done", []):
            keep["loaders_done"].append(s)
    store = _store_load()
    for i, e in enumerate(store):
        if e is drop:
            del store[i]
            break
    _REDIRECT[id(drop)] = (drop, keep)


def _canon(e):
    while id(e) in _REDIRECT:
        e = _REDIRECT[id(e)][1]
    return e

def _attach(ent, card):
    with _STORE_LOCK:
        side = "mr" if card["source"] == "Modrinth" else "cf"
        if ent.get(side):
            return
        for e in _store_load():
            if e is not ent and e.get(side) and e[side].get("id") == card.get("id"):
                _store_merge(ent, e)
                return
        ent[side] = card


def _resolve_other_side(ent, api_key):

#F23

    if ent.get("mr") and ent.get("cf"):
        return
    if ent.get("mr"):
        if not api_key:
            return
        base = ent["mr"]
        hit = cf_mod_by_slug(base["slug"], api_key) if base.get("slug") else None
        if hit and not _titles_similar(hit.get("name"), base.get("title")):
            hit = None
        if not hit:
            for h in cf_search(base.get("title") or "", api_key, limit=10):
                if _titles_similar(h.get("name"), base.get("title")):
                    hit = h
                    break
        if hit:
            _attach(ent, normalize_cf_hit(hit))
    elif ent.get("cf"):
        base = ent["cf"]
        proj = modrinth_project(base["slug"]) if base.get("slug") else None
        card = None
        if proj and proj.get("project_type", "mod") == "mod" and _titles_similar(proj.get("title"), base.get("title")):
            card = card_from_mr_project(proj)
        else:
            for h in modrinth_search_text(base.get("title") or ""):
                if _titles_similar(h.get("title"), base.get("title")):
                    card = normalize_modrinth_hit(h)
                    break
        if card:
            _attach(ent, card)

def _enrich(ent, api_key):
    with _STORE_LOCK:
        done = ent.setdefault("deps_done", [])
        ldone = ent.setdefault("loaders_done", [])
        todo = [side for side in ("mr", "cf") if ent.get(side) and not (side == "cf" and not api_key)]
    for side in todo:
        card = ent.get(side)
        if side not in done:
            deps = fetch_deps_for(card, api_key)
            with _STORE_LOCK:
                _merge_deps(ent, deps)
                done.append(side)
        if side not in ldone:
            loaders = modrinth_loader_versions(card.get("id") or card.get("slug")) if side == "mr" \
                else cf_loader_versions(card["id"], api_key)
            with _STORE_LOCK:
                _merge_loaders(ent, loaders)
                ldone.append(side)

def write_card_file(card, deps):
    try:
        store_add(card, deps, origin=T[LANG]['origin_manual'])
        return store_flush()
    except OSError as e:
        say(T[LANG]['save_error'].format(err=e))
        return None

#F24

def _render_entry(i, e, tr):
    mr, cf = e.get('mr'), e.get('cf')
    lines = ["[{}] {}".format(i, _ent_title(e))]
    if mr:
        lines.append("    Modrinth: {}  ({}: {})".format(mr.get('link'), tr['field_downloads'], mr.get('downloads', 0)))
    if cf:
        lines.append(f"    CurseForge: {cf.get('link')}  ({tr['field_downloads']}: {cf.get('downloads', 0)})")
    cats = []
    for card in (mr, cf):
        for c in (card or {}).get('categories') or []:
            if c and c not in cats:
                cats.append(c)
    lines.append(f"    {tr['field_categories']}: {', '.join(cats) or '-'}")
    loaders = e.get('loaders') or {}
    if loaders:
        lines.append(f"    {tr['f_loaders']}:")
        known = [n for n in LOADER_ORDER if n in loaders]
        extra = sorted(n for n in loaders if n not in LOADER_ORDER)
        for name in known + extra:
            vers = loaders.get(name)
            if vers:
                lines.append(f"      {name} ({', '.join(vers)})")
    dm = _ws(mr.get('description')) if mr else ""
    dc = _ws(cf.get('description')) if cf else ""
    if dm and dc and descriptions_differ(dm, dc):
        lines.append(f"    {tr['f_desc_mr']}: {dm}")
        lines.append(f"    {tr['f_desc_cf']}: {dc}")
    else:
        lines.append(f"    {tr['field_description']}: {dm or dc or '-'}")
    for kind in _DEP_KINDS:
        names = (e.get('deps') or {}).get(kind) or []
        if names:
            lines.append(f"    {DEP_TYPE_LABEL[kind][LANG]}: {', '.join(names)}")
    if e.get('origins'):
        lines.append(f"    {tr['f_found']}: {'; '.join(e['origins'])}")
    return lines

_DEP_TAG = {"required": "req", "optional": "opt", "incompatible": "inc", "embedded": "emb"}

def _render_entry_compact(e):
    mr, cf = e.get('mr'), e.get('cf')
    parts = [_ent_title(e)]

    dl = []
    if mr:
        dl.append(f"M{mr.get('downloads', 0)}")
    if cf:
        dl.append(f"C{cf.get('downloads', 0)}")
    if dl:
        parts.append("dl:" + ",".join(dl))

    cats = []
    for card in (mr, cf):
        for c in (card or {}).get('categories') or []:
            if c and c not in cats:
                cats.append(c)
    if cats:
        parts.append("cat:" + ",".join(cats))

    dm = _ws(mr.get('description')) if mr else ""
    dc = _ws(cf.get('description')) if cf else ""
    d = dm or dc
    if d:
        parts.append("desc:" + d)

    for kind in _DEP_KINDS:
        names = (e.get('deps') or {}).get(kind) or []
        if names:
            parts.append(f"{_DEP_TAG[kind]}:" + ",".join(names))

    loaders = e.get('loaders') or {}
    if loaders:
        known = [n for n in LOADER_ORDER if n in loaders]
        extra = sorted(n for n in loaders if n not in LOADER_ORDER)
        lp = [f"{name}({','.join(loaders[name])})" for name in known + extra if loaders.get(name)]
        if lp:
            parts.append("ld:" + ";".join(lp))

    links = [c.get('link') for c in (mr, cf) if c and c.get('link')]
    if links:
        parts.append("url:" + " ".join(links))

    return " | ".join(parts)

_FLUSH_T = {"t": 0.0}


def store_flush_throttled(interval=20):
    now = time.time()
    with _STORE_LOCK:
        if now - _FLUSH_T['t'] < interval:
            return
        _FLUSH_T['t'] = now
    try:
        store_flush()
    except OSError:
        pass


def store_flush():
    with _STORE_LOCK:
        return _store_flush_locked()

def _store_flush_locked():
    store = _store_load()
    tr = T[LANG]
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(STORE_PATH + ".tmp", "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)
    os.replace(STORE_PATH + ".tmp", STORE_PATH)

    #F25
    lines = [tr["file_header"].format(n=len(store), ts=time.strftime("%Y-%m-%d %H:%M")), ""]
    lines.append(_t(f"История запусков bulk (последние {RUN_LOG_TAIL}):", f"Bulk run history (last {RUN_LOG_TAIL}):"))
    try:
        with open(RUN_LOG_PATH, "r", encoding="utf-8") as rf:
            log_lines = rf.readlines()
        for entry in log_lines[-RUN_LOG_TAIL:]:
            lines.append("  " + entry.rstrip("\n"))
    except OSError:
        lines.append(_t("  (пока нет записей)", "  (nothing yet)"))
    lines.append("")
    for i, e in enumerate(store, 1):
        lines.extend(_render_entry(i, e, tr))
        lines.append("")
    with open(ALL_MODS_PATH + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    os.replace(ALL_MODS_PATH + ".tmp", ALL_MODS_PATH)

    #F26
    ai_lines = [f"# {len(store)} mods, updated {time.strftime('%Y-%m-%d %H:%M')}"]
    for i, e in enumerate(store, 1):
        ai_lines.append("{}. {}".format(i, _render_entry_compact(e)))
    with open(AI_MODS_PATH + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(ai_lines))
    os.replace(AI_MODS_PATH + ".tmp", AI_MODS_PATH)

    return ALL_MODS_PATH

def log_bulk_run(args_desc, total, new, addons):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} | запрос: {args_desc} | всего: {total} | новых: {new} | аддонов: {addons}\n"
    try:
        with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass

#F27

LAST_RESULTS = []

def do_search(args, api_key):
    tr = T[LANG]
    if not args:
        say(tr["search_usage"])
        return
    if not check_internet():
        say(f"{RED}{tr['no_internet']}{RESET}")
        return

    global LAST_RESULTS
    LAST_RESULTS = []
    results = []
    url_tasks = []
    plain_tags = []
    name_queries = []

    for a in args:
        nq = parse_name_arg(a)
        if nq is not None:
            if nq:
                name_queries.append(nq)
            else:
                say(f"{YELLOW}{tr['name_empty']}{RESET}")
        elif is_url(a):
            parsed = parse_listing_url(a)
            if parsed:
                for t in (parsed["tags"] or [None]):
                    if t:
                        url_tasks.append((parsed["source"], t))
            else:
                say(YELLOW + tr['url_not_recognized'].format(url=a) + RESET)
        else:
            plain_tags.append(a)

    cf_warned = False

    if plain_tags:
        mr_hits = modrinth_search(plain_tags)
        results += [normalize_modrinth_hit(h) for h in mr_hits]
        if api_key:
            cat_id = cf_category_id_for_tag(plain_tags[0], api_key)
            cf_hits = cf_search(" ".join(plain_tags), api_key, category_id=cat_id)
            results += [normalize_cf_hit(h) for h in cf_hits]
        else:
            say(f"{YELLOW}{tr['search_cf_skipped']}{RESET}")
            cf_warned = True

    for q in name_queries:
        results += [normalize_modrinth_hit(h) for h in modrinth_search_text(q, NAME_SEARCH_LIMIT)
                    if mr_name_ok(q, h)]
        if api_key:
            results += [normalize_cf_hit(h) for h in cf_search(q, api_key, limit=NAME_SEARCH_LIMIT)
                        if cf_name_ok(q, h)]
        elif not cf_warned:
            say(YELLOW + tr['search_cf_skipped'] + RESET)
            cf_warned = True

    for source, tag in url_tasks:
        if source == "modrinth":
            hits = modrinth_search([tag])
            results += [normalize_modrinth_hit(h) for h in hits]
        else:
            if not api_key:
                if not cf_warned:
                    say(f"{YELLOW}{tr['search_cf_skipped']}{RESET}")
                    cf_warned = True
                continue
            cat_id = cf_category_id_for_tag(tag, api_key)
            if not cat_id:
                say(tr["bulk_cf_category_not_found"].format(tag=tag))
                continue
            hits = cf_search("", api_key, category_id=cat_id)
            results += [normalize_cf_hit(h) for h in hits]

    dedup, seen = [], set()
    for r in results:
        key = (r["source"], r["id"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)
    results = dedup

    say(f"{GREEN}{BOLD}{tr['search_header'].format(tags=', '.join(args))}{RESET}")
    if not results:
        say(tr["search_none"])
        say(tr["commands"])
        return

    for idx, r in enumerate(results, start=1):
        say(f"[{idx}] {BOLD}{r['title']}{RESET} ({r['source']}, {r['downloads']} ↓)")
        #F28
        if r["description"]:
            say(f"    {r['description']}")
    LAST_RESULTS = results
    say(tr["commands"])


def _get_result(idx_str):
    tr = T[LANG]
    if not LAST_RESULTS:
        say(tr["no_results_yet"])
        return None
    try:
        idx = int(idx_str)
    except ValueError:
        say(tr["bad_index"])
        return None
    if not (1 <= idx <= len(LAST_RESULTS)):
        say(tr["bad_index"])
        return None
    return LAST_RESULTS[idx - 1]

def _print_card(card, api_key):
    tr = T[LANG]
    say(f"{GREEN}{BOLD}{tr['show_header'].format(title=card['title'])}{RESET}")
    say(f"{tr['field_source']}: {card['source']}")
    say(f"{tr['field_link']}: {card['link']}")
    say(f"{tr['field_downloads']}: {card['downloads']}")
    say(f"{tr['field_categories']}: {', '.join(card['categories']) or '-'}")
    say(f"{tr['field_description']}: {card['description'] or '-'}")

    deps = fetch_deps_for(card, api_key)
    any_deps = False
    for kind in _DEP_KINDS:
        if deps[kind]:
            any_deps = True
            say(f"{DEP_TYPE_LABEL[kind][LANG]}:")
            for name in deps[kind]:
                say(f"  - {name}")
    if not any_deps:
        say(tr["field_deps_none"])
    say(tr["field_deps_note"])
    return deps

def do_show(args, api_key):
    tr = T[LANG]
    if not args:
        say(tr["bad_index"])
        return
    card = _get_result(args[0])
    if not card:
        return
    _print_card(card, api_key)
    say(tr["commands"])


def do_save(args, api_key):
    tr = T[LANG]
    if not args:
        say(tr["bad_index"])
        return
    card = _get_result(args[0])
    if not card:
        return
    deps = fetch_deps_for(card, api_key)
    path = write_card_file(card, deps)
    if path:
        say(tr["save_done"].format(path=os.path.relpath(path, SCRIPT_DIR)))
    say(tr["commands"])

def do_saveall(api_key):
    tr = T[LANG]
    if not LAST_RESULTS:
        say(tr["no_results_yet"])
        return
    n = 0
    try:
        for card in LAST_RESULTS:
            store_add(card, fetch_deps_for(card, api_key), origin=tr["origin_manual"])
            n += 1
        path = store_flush()
        say(tr["saveall_done"].format(n=n))
        say(tr["save_done"].format(path=os.path.relpath(path, SCRIPT_DIR)))
    except OSError as e:
        say(tr["save_error"].format(err=e))
    say(tr["commands"])

def find_dependents(targets, api_key, on_found=None):
    tr = T[LANG]
    mr_ids, cf_ids = {}, {}
    for e in targets:
        if e.get("mr"):
            mr_ids[e["mr"]["id"]] = e
        if e.get("cf"):
            cf_ids[e["cf"]["id"]] = e

    pool_mr, pool_cf = {}, {}
    pool_lock = threading.Lock()
    cprog = {"done": 0}
    say(tr["bulk_collect"].format(n=len(targets)))

    def _collect(e):
        title = _ent_title(e)
        nt = _blob(title)
        if not nt:
            return
        mr_new = [h for h in modrinth_search_text(title, ADDON_SEARCH_LIMIT)
                  if nt in _blob(h.get("title"), h.get("slug"), h.get("description"))]
        cf_new = []
        if api_key:
            cf_new = [h for h in cf_search(title, api_key, limit=ADDON_SEARCH_LIMIT)
                      if nt in _blob(h.get("name"), h.get("slug"), h.get("summary"))]
        with pool_lock:
            for h in mr_new:
                pid = h.get("project_id")
                if pid and pid not in mr_ids:
                    pool_mr.setdefault(pid, h)
            for h in cf_new:
                cid = h.get("id")
                if cid and cid not in cf_ids:
                    pool_cf.setdefault(cid, h)
            cprog["done"] += 1
            if cprog["done"] % 50 == 0:
                say(tr["bulk_progress"].format(done=cprog["done"], n=len(targets)))

    _parallel_map(_collect, targets)

    n = len(pool_mr) + len(pool_cf)
    say(tr["bulk_addons"].format(n=n))
    found = []
    progress = {"done": 0}
    lock = threading.Lock()

    def _bump():
        with lock:
            progress["done"] += 1
            if progress["done"] % 25 == 0:
                say(tr["bulk_progress"].format(done=progress["done"], n=n))

    def _check_mr(item):
        pid, h = item
        matches = [(mr_ids[dp], dt) for dt, dp, _fn in modrinth_latest_version_deps(pid)
                   if dp in mr_ids and dt in ("required", "optional")]
        _bump()
        if matches:
            card = normalize_modrinth_hit(h)
            found.append((card, matches))
            if on_found:
                on_found(card, matches)

    def _check_cf(item):
        cid, h = item
        matches = [(cf_ids[dp], dk) for dk, dp in cf_latest_file_deps(cid, api_key)
                   if dp in cf_ids and dk in ("required", "optional")]
        _bump()
        if matches:
            card = normalize_cf_hit(h)
            found.append((card, matches))
            if on_found:
                on_found(card, matches)

    _parallel_map(_check_mr, pool_mr.items())
    if api_key:
        _parallel_map(_check_cf, pool_cf.items())
    return found


def do_bulk(args, api_key):
    dbg = False
    tr = T[LANG]
    if not args:
        say(tr["bulk_usage"])
        return
    if not check_internet():
        say(f"{RED}{tr['no_internet']}{RESET}")
        return
    tasks = []
    for a in args:
        nq = parse_name_arg(a)
        if nq is not None:
            if not nq:
                say(f"{YELLOW}{tr['name_empty']}{RESET}")
                continue
            base = {"loaders": [], "versions": [], "env": "", "sort": "relevance", "query": nq}
            tasks.append(dict(base, source="modrinth", tags=[]))
            if api_key:
                tasks.append(dict(base, source="curseforge", tags=[]))
        elif is_url(a):
            p = parse_listing_url(a)
            if p:
                tasks.append(p)
            else:
                say(YELLOW + tr['url_not_recognized'].format(url=a) + RESET)
        else:
            base = {"loaders": [], "versions": [], "env": "", "sort": "downloads"}
            tasks.append(dict(base, source="modrinth", tags=[a]))
            if api_key:
                tasks.append(dict(base, source="curseforge", tags=[a]))
    if not tasks:
        return

    _CANCEL.clear()
    store = _store_load()
    before = len(store)
    say(f"{GREEN}{BOLD}{tr['bulk_header'].format(query=', '.join(args))}{RESET}")
    say(tr["bulk_thresholds"].format(pages=TOP_PAGES, size=PAGE_SIZE, addons=ADDON_SEARCH_LIMIT, workers=HTTP_WORKERS))
    say()

    top, addon_ents = [], []
    cf_warned = False
    try:
        for t in tasks:
            label = "+".join(t["tags"] + t.get("loaders", []))
            if t["source"] == "modrinth":
                if t.get("query"):
                    say(tr["bulk_fetching_name"].format(source="Modrinth", q=t["query"]))
                    origin = tr["origin_name"].format(src="modrinth", q=t["query"])
                else:
                    say(tr["bulk_fetching"].format(source="Modrinth", tag=label))
                    origin = tr["origin_top"].format(src="modrinth", tag=label)
                for hit in modrinth_top(t):
                    top.append(store_add(normalize_modrinth_hit(hit), None, origin))
            else:
                if not api_key:
                    if not cf_warned:
                        say(f"{YELLOW}{tr['search_cf_skipped']}{RESET}")
                        cf_warned = True
                    continue
                if t.get("query"):
                    say(tr["bulk_fetching_name"].format(source="CurseForge", q=t["query"]))
                    origin = tr["origin_name"].format(src="curseforge", q=t["query"])
                    for item in cf_name_top(t["query"], api_key):
                        top.append(store_add(normalize_cf_hit(item), None, origin))
                    continue
                for tag in t["tags"]:
                    cat_id = cf_category_id_for_tag(tag, api_key)
                    if not cat_id:
                        say(tr["bulk_cf_category_not_found"].format(tag=tag))
                        continue
                    say(tr["bulk_fetching"].format(source="CurseForge", tag=tag))
                    for item in cf_top(cat_id, api_key, t.get("cf_sort", 6)):
                        top.append(store_add(normalize_cf_hit(item), None,
                                             tr["origin_top"].format(src="curseforge", tag=tag)))
        store_flush()

        def uniq(ents):
            out, seen = [], set()
            for e in ents:
                e = _canon(e)
                if id(e) not in seen:
                    seen.add(id(e))
                    out.append(e)
            return out

        top = uniq(top)
        say(tr["bulk_resolving"].format(n=len(top)))
        _parallel_map(lambda e: _resolve_other_side(e, api_key), top)
        top = uniq(top)
        _parallel_map(lambda e: _enrich(e, api_key), top)
        store_flush()
        save_cache()

        def _on_addon_found(card, matches):
            ent = None
            for te, dk in matches:
                ent = store_add(card, None, tr["origin_addon"].format(name=_ent_title(_canon(te)), dep=dk))
            if ent is not None:
                addon_ents.append(ent)
            store_flush_throttled()

        find_dependents(top, api_key, on_found=_on_addon_found)
        addon_ents = uniq(addon_ents)
        say(tr["bulk_addons_found"].format(n=len(addon_ents)))
        _parallel_map(lambda e: _resolve_other_side(e, api_key), addon_ents)
        addon_ents = uniq(addon_ents)
        _parallel_map(lambda e: _enrich(e, api_key), addon_ents)
    except KeyboardInterrupt:
        say()
        say(f"{YELLOW}{tr['bulk_interrupted']}{RESET}")
    finally:
        try:
            path = store_flush()
        except OSError as e:
            say(tr["save_error"].format(err=e))
            path = ALL_MODS_PATH
        save_cache() #Ftemp84

    say()
    new_count = max(0, len(store) - before)
    log_bulk_run(", ".join(args), len(store), new_count, len(addon_ents))
    say(tr["bulk_done_single"].format(total=len(store), new=new_count, addons=len(addon_ents),
                                      path=os.path.relpath(path, SCRIPT_DIR),
                                      ai_path=os.path.relpath(AI_MODS_PATH, SCRIPT_DIR)))
    say(tr["commands"])

def do_addons(args, api_key):
    tr = T[LANG]
    if not args:
        say(tr['addons_usage'])
        return
    if not check_internet():
        say(f"{RED}{tr['no_internet']}{RESET}")
        return
    query = args[0]
    target = None
    mr_target = modrinth_project(query)
    if mr_target and mr_target.get('project_type', "mod") != "mod":
        mr_target = None
    if mr_target:
        target = {'id': mr_target.get('id'), 'slug': mr_target.get('slug'), 'title': mr_target.get('title', query)}
    elif api_key:
        cf_target = cf_mod_by_slug(query, api_key) or cf_mod_by_id(query, api_key)
        if cf_target and cf_target.get('classId') not in (None, CF_CLASS_ID_MODS):
            cf_target = None
        if cf_target:
            target = {'id': cf_target.get('id'), 'slug': cf_target.get('slug'), 'title': cf_target.get('name', query)}

    if not target:
        say(tr['addons_target_not_found'])
        return

    say(GREEN + BOLD + tr['addons_header'].format(name=target['title']) + RESET)
    say(tr['addons_disclaimer'])
    say()

    candidates = modrinth_search_text(target['title'])
    say(tr['addons_checking'].format(n=len(candidates)))

    confirmed = []
    for hit in candidates:
        proj_id = hit.get('project_id')
        if not proj_id or proj_id == target['id']:
            continue
        for dep_type, dep_proj_id, _fn in modrinth_latest_version_deps(proj_id):
            if dep_proj_id == target['id'] and dep_type in ("required", "optional"):
                confirmed.append((hit.get('title', proj_id), dep_type, "Modrinth"))
                break

    cf_candidates = cf_search(target['title'], api_key) if api_key else []
    if api_key:
        for hit in cf_candidates:
            cf_id = hit.get('id')
            if not cf_id or cf_id == target['id']:
                continue
            for kind, dep_id in cf_latest_file_deps(cf_id, api_key):
                if dep_id == target['id'] and kind in ("required", "optional"):
                    confirmed.append((hit.get('name', cf_id), kind, "CurseForge"))
                    break

    say()
    if confirmed:
        say(tr['addons_confirmed'].format(name=target['title']))
        for name, dep_type, source in confirmed:
            say(f"  - {BOLD}{name}{RESET} ({source}, {dep_type})")
        for name, dep_type, source in confirmed:
            pool = candidates if source == "Modrinth" else cf_candidates
            for hit in pool:
                hit_name = hit.get('title') if source == "Modrinth" else hit.get('name')
                if hit_name == name:
                    card = normalize_modrinth_hit(hit) if source == "Modrinth" else normalize_cf_hit(hit)
                    deps = fetch_deps_for(card, api_key)
                    write_card_file(card, deps)
                    break
    else:
        say(tr['addons_none_confirmed'].format(name=target['title']))
    say(tr['commands'])

def do_help():
    tr = T[LANG]
    say(f"{GREEN}{BOLD}{tr['help_header']}{RESET}")
    for cmd, key in [
        ("key <ключ>", "help_key"), ("search <тег|name:название|ссылка ...>", "help_search"), ("show <N>", "help_show"),
        ("save <N>", "help_save"), ("saveall", "help_saveall"), ("bulk <тег|name:название|ссылка ...>", "help_bulk"),
        ("addons <slug|modid>", "help_addons"),
        ("build <ссылка|slug> [загрузчик] [версия] [mr=N] [cf=N]", "help_build"),
        ("newaddons <ссылка|slug> [период] [загрузчик] [версия]", "help_newaddons"),
        ("importlink [prefer CF|M] [min mr=N cf=N]", "help_importlink"),
        ("update", "help_update"),
    ]:
        say()
        say("  " + BOLD + str(cmd) + RESET)
        say(f"      {tr[key]}")
    say()
    say("  " + BOLD + "slug" + RESET)
    say(f"      {tr['help_slug']}")

def load_cf_key():
    try:
        with open(CF_KEY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                return line
    except OSError:
        return None
    return None

def save_cf_key(value):
    try:
        with open(CF_KEY_PATH, "w", encoding="utf-8") as f:
            f.write(CF_KEY_HEADER)
            f.write(value.strip() + "\n")
    except OSError:
        pass

def print_banner():
    tr = T[LANG]
    print("\n" * 30)
    print(GREEN + BOLD + "================================================" + RESET)
    print(GREEN + BOLD + tr['banner_title'] + RESET)
    print(GREEN + tr['banner_note'] + RESET)
    print(f"{GREEN}{BOLD}================================================{RESET}")
    print()
    print(tr["commands"])



def choose_language():
    global LANG
    while True:
        try:
            choice = input("Выберите язык / Choose language [ru/en]: ").strip().lower()
        except EOFError:
            LANG = "ru"
            return
        if choice in ("ru", "en"):
            LANG = choice
            return
        if not choice:
            LANG = "ru"
            return


MAIN_LIMIT = 150      #F31
SUB_ADDON_LIMIT = 30      #F32
MAX_DEPTH = 5         #F33
POSSIBLE_LIMIT = 40   #F34
DL_WORKERS = 4        #F35
LOADERS = ("forge", "neoforge", "fabric", "quilt")
LOADER_LABEL = {"forge": "Forge", "neoforge": "NeoForge", "fabric": "Fabric", "quilt": "Quilt"}
CF_LOADER_IDS = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
PACKS_DIR = os.path.join(OUTPUT_DIR, "modpacks")
ANSWERS_PATH = os.path.join(OUTPUT_DIR, ".build_answers.json")
REL_VER_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")

def _vtup(v):
    t = tuple(int(x) for x in re.findall(r"\d+", v or ""))
    return (t + (0, 0, 0))[:3]

def _ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        say()
        return None

def _slug_of(ent):
    base = ""
    for side in ("mr", "cf"):
        if ent.get(side) and ent[side]["card"].get("slug"):
            base = ent[side]["card"]["slug"]
            break
    return re.sub(r"[^a-z0-9_-]+", "-", (base or ent["title"]).lower()).strip("-") or "mod"

def _qname(title):
    q = _ws(re.sub(r"[\(\[].*?[\)\]]", " ", title or ""))
    return q or (title or "")

#F36

def _norm_pres(label_map):
    out = {}
    for label, vers in (label_map or {}).items():
        name = str(label).lower()
        if name not in LOADERS:
            continue
        good = set(v for v in (vers or []) if REL_VER_RE.match(v or ""))
        if good:
            out.setdefault(name, set()).update(good)
    return out

def cf_presence(hit):
    out = {}
    for idx in hit.get("latestFilesIndexes") or []:
        gv = idx.get("gameVersion")
        if not REL_VER_RE.match(gv or ""):
            continue
        name = (CF_MODLOADER_NAME.get(idx.get("modLoader")) or "").lower()
        if not name and _vtup(gv) < (1, 14, 0):
            name = "forge"          #F37
        if name in LOADERS:
            out.setdefault(name, set()).add(gv)
    return out

def slim_cf_hit(h):
    links = h.get("links") or {}
    return {"id": h.get("id"), "slug": h.get("slug"), "name": h.get("name"), "summary": h.get("summary"),
            "downloadCount": h.get("downloadCount", 0), "classId": h.get("classId"),
            "links": {"websiteUrl": links.get("websiteUrl")},
            "categories": [{"name": c.get("name")} for c in (h.get("categories") or [])],
            "pres": dict((k, sorted(v)) for k, v in cf_presence(h).items()),
            "sha1": cf_sha1s(h)}

def mr_record(card):
    pid = card["id"]
    deps = modrinth_latest_version_deps(pid) or []
    pres = _norm_pres(modrinth_loader_versions(pid))
    edges = [(d[0], d[1]) for d in deps if len(d) >= 2 and d[1] and d[0] in ("required", "optional", "incompatible")]
    return {"side": "mr", "id": pid, "card": card, "pres": pres, "edges": edges, "linked": False, "name_match": False}


def cf_record(slim, api_key, with_deps=True):
    cid = slim.get('id')
    deps = (cf_latest_file_deps(cid, api_key) or []) if with_deps else []
    pres = dict((k, set(v)) for k, v in (slim.get('pres') or {}).items())
    edges = [(d[0], d[1]) for d in deps if len(d) >= 2 and d[1] and d[0] in ("required", "optional", "incompatible")]
    return {'side': "cf", 'id': cid, 'card': normalize_cf_hit(slim), 'pres': pres, 'edges': edges,
            'linked': False, 'name_match': False, 'hashes': list(slim.get('sha1') or [])}

#F38

def mr_bsearch(title, limit):
    pages = max(1, -(-limit // PAGE_SIZE))
    key = f"mr_bsearch_v1z:{title.lower()}:{pages}:{PAGE_SIZE}"
    cached = cache_get(key)
    if cached != "MISS":
        return cached
    hits, status = _mr_pages([["project_type:mod"]], "relevance", title, pages)
    slim = [dict((k, h.get(k)) for k in ("project_id", "slug", "title", "description", "downloads", "categories"))
            for h in mr_only_mods(hits)]
    if status == "ok":
        cache_set(key, slim)
    return slim


def cf_bsearch(title, api_key, limit):
    pages = max(1, -(-limit // PAGE_SIZE))
    key = f"cf_bsearch_v2x:{title.lower()}:{pages}:{PAGE_SIZE}"
    cached = cache_get(key)
    if cached != "MISS":
        return cached
    items, ok = [], True
    for p in range(pages):
        url = ("https://api.curseforge.com/v1/mods/search?gameId=432&classId={}&searchFilter={}"
               "&pageSize={}&index={}&sortField=2&sortOrder=desc").format(
                   CF_CLASS_ID_MODS, urllib.parse.quote(title), PAGE_SIZE, p * PAGE_SIZE)
        data = http_get_json(url, headers=cf_headers(api_key))
        if data is None:
            ok = False
            break
        page = data.get("data", [])
        items.extend(page)
        if len(page) < PAGE_SIZE:
            break
    slim = [slim_cf_hit(h) for h in cf_only_mods(items)]
    if ok:
        cache_set(key, slim)
    return slim


def mr_by_slug(slug):
    key = "mr_bslug_v1k:" + str(slug).lower()
    cached = cache_get(key)
    if cached != "MISS":
        return cached
    p = http_get_json("https://api.modrinth.com/v2/project/" + urllib.parse.quote(str(slug), safe=""))
    if not isinstance(p, dict):
        return None
    slim = dict((k, p.get(k)) for k in ("id", "slug", "title", "description", "downloads", "categories", "project_type"))
    cache_set(key, slim)
    return slim


def cf_by_slug(slug, api_key):
    key = "cf_bslug_v2v:" + str(slug).lower()
    cached = cache_get(key)
    if cached != "MISS":
        return cached
    data = http_get_json("https://api.curseforge.com/v1/mods/search?gameId=432&classId={}&slug={}".format(
        CF_CLASS_ID_MODS, urllib.parse.quote(str(slug))), headers=cf_headers(api_key))
    if data is None:
        return None
    items = cf_only_mods(data.get('data', []))
    slim = slim_cf_hit(items[0]) if items else None
    cache_set(key, slim)
    return slim

def other_on_cf(card, api_key):
    slim = cf_by_slug(card["slug"], api_key) if card.get("slug") else None
    if slim and _titles_similar(slim.get("name"), card.get("title")):
        return slim
    for h in cf_bsearch(_qname(card.get("title")), api_key, 10):
        if _titles_similar(h.get("name"), card.get("title")):
            return h
    return None


def other_on_mr(card):
    proj = mr_by_slug(card["slug"]) if card.get("slug") else None
    if proj and proj.get("project_type") in (None, "mod") and _titles_similar(proj.get("title"), card.get("title")):
        return card_from_mr_project(proj)
    for h in modrinth_search_text(_qname(card.get("title"))):
        if _titles_similar(h.get("title"), card.get("title")):
            return normalize_modrinth_hit(h)
    return None


def find_main_mod(target, api_key):
    slug, side = target, None
    if is_url(target):
        pu = urllib.parse.urlparse(target)
        parts = [p for p in pu.path.split("/") if p]
        if "modrinth.com" in pu.netloc.lower() and len(parts) >= 2:
            side, slug = "mr", parts[1]
        elif "curseforge.com" in pu.netloc.lower() and len(parts) >= 3:
            side, slug = "cf", parts[2]
        else:
            return None, None
    mr_card, cf_slim = None, None
    if side in (None, "mr"):
        p = mr_by_slug(slug)
        if p and p.get("project_type") in (None, "mod"):
            mr_card = card_from_mr_project(p)
    if api_key and (side == "cf" or (side is None and not mr_card)):
        cf_slim = cf_by_slug(slug, api_key)
        if not cf_slim and str(slug).isdigit():
            raw = cf_mod_by_id(slug, api_key)
            if raw and raw.get("classId") in (None, CF_CLASS_ID_MODS):
                cf_slim = slim_cf_hit(raw)
    if mr_card and not cf_slim and api_key:
        cf_slim = other_on_cf(mr_card, api_key)
    elif cf_slim and not mr_card:
        mr_card = mr_for_cf(normalize_cf_hit(cf_slim), cf_slim.get("sha1"))
    return mr_card, cf_slim

#F39

def new_world(title, mr_rec, cf_rec):
    main = {"n": 0, "title": title, "mr": None, "cf": None, "main": True, "edges": {}}
    W = {"ents": [main], "by_mr": {}, "by_cf": {}, "pool": [], "seen_mr": set(), "seen_cf": set(),
         "lock": threading.RLock()}
    for rec in (mr_rec, cf_rec):
        if rec:
            _reg(W, main, rec)
    return W


def _reg(W, ent, rec):
    ent[rec["side"]] = rec
    rec["linked"] = True
    W["by_" + rec["side"]][rec["id"]] = ent
    W["seen_" + rec["side"]].add(rec["id"])



def _entity_for(W, rec):
    with W["lock"]:
        card, side = rec["card"], rec["side"]
        for e in W["ents"]:
            if e.get(side):
                continue
            base = (e.get("mr") or e.get("cf"))["card"]
            same_slug = bool(card.get("slug")) and card["slug"].lower() == (base.get("slug") or "").lower()
            if (same_slug or norm_title(card.get("title")) == norm_title(base.get("title"))) \
                    and _titles_similar(base.get("title"), card.get("title")):
                _reg(W, e, rec)
                return e, False
        ent = {"n": len(W["ents"]), "title": card.get("title") or "?", "mr": None, "cf": None, "edges": {}}
        W["ents"].append(ent)
        _reg(W, ent, rec)
        return ent, True


def collect_addons(W, frontier, api_key, limit, opts):
    found_mr, found_cf = {}, {}
    lock=threading.Lock()

    def one(ent):
        title = _qname(ent['title'])
        nt = _blob(title)
        if len(nt) < 3:
            return
        mr_hits = mr_bsearch(title, limit)
        cf_hits = cf_bsearch(title, api_key, limit) if api_key else []
        with lock:
            for h in mr_hits:
                pid = h.get('project_id')
                if not pid or pid in W['seen_mr'] or pid in found_mr:
                    continue
                if (h.get('downloads') or 0) < opts['mr']:
                    continue
                if nt in _blob(h.get('title'), h.get('slug'), h.get('description')):
                    found_mr[pid] = h
            for h in cf_hits:
                cid = h.get('id')
                if not cid or cid in W['seen_cf'] or cid in found_cf:
                    continue
                if (h.get('downloadCount') or 0) < opts['cf']:
                    continue
                if nt in _blob(h.get('name'), h.get('slug'), h.get('summary')):
                    found_cf[cid] = h

    _parallel_map(one, frontier)
    W['seen_mr'].update(found_mr)
    W['seen_cf'].update(found_cf)
    return found_mr, found_cf


def verify_edges(W, found_mr, found_cf, api_key, main_nt):
    total = len(found_mr) + len(found_cf)
    prog = {"n": 0}
    lock = threading.Lock()

    def done(rec):
        with lock:
            W["pool"].append(rec)
            prog["n"] += 1
            if prog["n"] % 25 == 0:
                say(_t("  проверено {}/{}", "  checked {}/{}").format(prog["n"], total))

    def one_mr(h):
        rec = mr_record(normalize_modrinth_hit(h))
        rec["name_match"] = main_nt in _blob(rec["card"].get("title"), rec["card"].get("slug"))
        done(rec)

    def one_cf(h):
        rec = cf_record(h, api_key)
        rec["name_match"] = main_nt in _blob(rec["card"].get("title"), rec["card"].get("slug"))
        done(rec)

    _parallel_map(one_mr, list(found_mr.values()))
    _parallel_map(one_cf, list(found_cf.values()))

def _link_pass(W):
    new_ents = []
    changed = True
    while changed:
        changed = False
        for rec in list(W["pool"]):
            if rec["linked"]:
                continue
            known = W["by_" + rec["side"]]
            if rec.get("force") or any(k in ("required", "optional") and t in known for k, t in rec["edges"]):
                ent, is_new = _entity_for(W, rec)
                changed = True
                if is_new:
                    new_ents.append(ent)
    return new_ents

def fill_other_side(W, ent, api_key, opts):
    if ent.get("mr") and ent.get("cf"):
        return
    if ent.get("mr"):
        if not api_key:
            return
        slim = other_on_cf(ent["mr"]["card"], api_key)
        if not slim:
            return
        if (slim.get("downloadCount") or 0) < opts["cf"] or slim["id"] in W["by_cf"]:
            return
        rec = cf_record(slim, api_key)
    else:
        card = mr_for_cf(ent["cf"]["card"], ent["cf"].get("hashes"))
        if not card or (card.get("downloads") or 0) < opts["mr"] or card["id"] in W["by_mr"]:
            return
        rec = mr_record(card)
    with W["lock"]:
        if not ent.get(rec["side"]) and rec["id"] not in W["by_" + rec["side"]]:
            _reg(W, ent, rec)

def link_all(W, api_key, opts):
    got = []
    while True:
        batch = _link_pass(W)
        if not batch:
            return got
        got.extend(batch)
        _parallel_map(lambda e: fill_other_side(W, e, api_key, opts), batch)


def analyze_world(W, api_key, opts, main_nt):
    frontier = [W["ents"][0]]
    depth = 0
    while frontier and depth < MAX_DEPTH:
        depth += 1
        limit=MAIN_LIMIT if depth == 1 else SUB_ADDON_LIMIT
        say(_t("Шаг {}: ищу аддоны, модов в проверке: {}...", "Step {}: looking for addons, mods to check: {}...").format(
            depth, len(frontier)))
        found_mr, found_cf = collect_addons(W, frontier, api_key, limit, opts)
        say(_t("  кандидатов: {} (Modrinth {}, CurseForge {})", "  candidates: {} (Modrinth {}, CurseForge {})").format(
                    len(found_mr) + len(found_cf), len(found_mr), len(found_cf)))
        verify_edges(W, found_mr, found_cf, api_key, main_nt)
        frontier = link_all(W, api_key, opts)
        say(_t("  аддонов на этом шаге: {}", "  addons on this step: {}").format(len(frontier)))
        save_cache()

#F40

def _ent_pres(ent):
    out = {}
    for side, tag in (("mr", "M"), ("cf", "CF")):
        rec = ent.get(side)
        if rec:
            for loader, vers in rec["pres"].items():
                for v in vers:
                    out.setdefault((loader, v), set()).add(tag)
    return out


def aggregate(W):
    main = W['ents'][0]
    for e in W['ents']:
        e['edges'] = {}
        e['pmap'] = _ent_pres(e)
        for side in ("mr", "cf"):
            rec = e.get(side)
            if not rec:
                continue
            known = W["by_" + side]
            for kind, tid in rec['edges']:
                t = known.get(tid)
                if t is None or t is e or kind not in ("required", "optional"):
                    continue
                if e['edges'].get(t['n']) != "required":
                    e['edges'][t['n']] = kind
        if e is not main and any((e.get(s) or {}).get('force') for s in ("mr", "cf")):
            e['edges'][main['n']] = "required"

def members_of(ents, main, key):
    #F71
    req, lnk = set([main['n']]), set([main['n']])
    cand = [e for e in ents if e is not main and key in e['pmap']]
    changed = True
    while changed:
        changed = False
        for e in cand:
            n = e['n']
            if n not in req and any(k == "required" and t in req for t, k in e['edges'].items()):
                req.add(n)
                lnk.add(n)
                changed = True
            elif n not in lnk and any(t in lnk for t in e['edges']):
                lnk.add(n)
                changed = True
    return req, lnk


def make_blocks(W, opts):
    cnt = 0
    ents, main = W["ents"], W["ents"][0]
    blocks = []
    for key in sorted(main["pmap"]):
        if opts["loaders"] and key[0] not in opts["loaders"]:
            continue
        if opts["versions"] and key[1] not in opts["versions"]:
            continue
        req, lnk = members_of(ents, main, key)
        blocks.append({"key": key,
                       "req": [e for e in ents if e["n"] in req and e is not main],
                       "opt": [e for e in ents if e["n"] in lnk and e["n"] not in req]})
    #F41
    for loader in LOADERS:
        same=sorted([b for b in blocks if b["key"][0] == loader], key=lambda b: _vtup(b["key"][1]))
        vers = [b["key"][1] for b in same]
        where = {}
        for b in same:
            for e in b["req"] + b["opt"]:
                where.setdefault(e["n"], []).append(b["key"][1])
        for b in same:
            here = set(e["n"] for e in b["req"] + b["opt"])
            b["excl"], b["absent"] = set(), {}
            for e in b["req"] + b["opt"]:
                w = where[e["n"]]
                if len(vers) >= 2 and len(w) == 1:
                    b["excl"].add(e["n"])
                else:
                    b["absent"][e["n"]] = [v for v in vers if v not in w]
            b["elsewhere"] = [(ents[n], w) for n, w in where.items() if n not in here]
    blocks.sort(key=lambda b: (-len(b["req"]), tuple(-x for x in _vtup(b["key"][1])), b["key"][0]))
    return blocks

#F42

def answers_load():
    try:
        with open(ANSWERS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def answers_save(d):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def plat_tag(plats):
    if "M" in plats and "CF" in plats:
        return "[M x CF]"
    return "[M]" if "M" in plats else "[CF]"

def ask_possible(W, opts, api_key):
    main = W['ents'][0]
    keys = set(k for k in _ent_pres(main) if (not opts['loaders'] or k[0] in opts['loaders'])
               and (not opts['versions'] or k[1] in opts['versions']))
    cands = []
    for rec in W['pool']:
        if rec['linked'] or not rec['name_match']:
            continue
        if not any((lo, v) in keys for lo, vs in rec['pres'].items() for v in vs):
            continue
        title = rec['card'].get('title') or "?"
        for c in cands:
            if rec['side'] not in c['recs'] and _titles_similar(c['title'], title):
                c['recs'][rec['side']] = rec
                break
        else:
            cands.append({'title': title, 'key': norm_title(title), 'recs': {rec['side']: rec}})
    answers = answers_load()
    mine = answers.setdefault(norm_title(main['title']), {'yes': [], 'no': []})
    ask, forced = [], False
    for c in cands:
        if c['key'] in mine['yes']:
            for r in c['recs'].values():
                r['force'] = True
            forced = True
        elif c['key'] not in mine['no']:
            ask.append(c)
    ask.sort(key=lambda c: -sum((r['card'].get('downloads') or 0) for r in c['recs'].values()))
    ask = ask[:POSSIBLE_LIMIT]
    if ask:
        say()
        say(f"{GREEN}{BOLD}" + _t("=== Возможные аддоны: название похоже, а зависимости на '{}' нет ===", "=== Possible addons: similar name but no dependency on '{}' ===").format(
                                   main['title']) + RESET)
        for i, c in enumerate(ask, 1):
            tags = plat_tag(set({'mr': "M", 'cf': "CF"}[s] for s in c['recs']))
            links = " | ".join(r['card'].get('link') or "" for r in c['recs'].values())
            say("{}) {} {}  {}".format(i, c['title'], tags, links))
        ans = _ask(_t("Это аддон к '{}'? Номера через пробел (a = все, Enter = нет): ", "Addon of '{}'? Numbers with spaces (a = all, Enter = no): ").format(
                                 main['title']))
        if ans is not None:
            pick = set()
            for tok in ans.replace(",", " ").split():
                if tok.lower() in ("a", "all", "все"):
                    pick = set(range(1, len(ask) + 1))
                elif tok.isdigit() and 1 <= int(tok) <= len(ask):
                    pick.add(int(tok))
            for i, c in enumerate(ask, 1):
                if i in pick:
                    mine['yes'].append(c['key'])
                    for r in c['recs'].values():
                        r['force'] = True
                    forced = True
                else:
                    mine['no'].append(c['key'])
            answers_save(answers)
    if forced:
        link_all(W, api_key, opts)



#F43

def dl_count(e):
    return sum((e[s]["card"].get("downloads") or 0) for s in ("mr", "cf") if e.get(s))


def sorted_by_dl(lst, b):
    return sorted(lst, key=lambda e: (e['n'] not in b['excl'], -dl_count(e), e['title'].lower()))

def block_head(b):
    s = _t("{} {} - найдено аддонов: {}", "{} {} - addons found: {}").format(
        LOADER_LABEL[b["key"][0]], b["key"][1], len(b["req"]))
    if b["opt"]:
        s += _t(" (+{} необязательных)", " (+{} optional)").format(len(b["opt"]))
    return s

def block_line(e, b, links, cut):
    s = e['title'] + " " + plat_tag(e['pmap'].get(b['key'], set()))
    if e['n'] in b['excl']:
        s="exclusive " + s
    elif b['absent'].get(e['n']):
        a = b['absent'][e['n']]
        if cut and len(a) > cut:
            a = a[:cut] + ["..."]
        s += _t(" (нет на: ", " (missing on: ") + ", ".join(a) + ")"
    if links:
        urls = [e[s2]['card'].get('link') for s2 in ("mr", "cf") if e.get(s2) and e[s2]['card'].get('link')]
        s += "  " + " | ".join(urls)
        if any((e.get(s2) or {}).get('force') for s2 in ("mr", "cf")):
            s += _t("    (подтверждён вручную)", "  (confirmed by hand)")
    return s


def print_blocks(main, blocks):
    say()
    say(f"{GREEN}{BOLD}" + _t("=== Сборки для мода: {} ===", "=== Builds for mod: {} ===").format(main["title"]) + RESET)
    for i, b in enumerate(blocks, 1):
        say(BOLD + f"[{i}] {block_head(b)}" + RESET)
        for e in sorted_by_dl(b["req"], b):
            say("  " + block_line(e, b, False, 6))
        if b["opt"]:
            say("  " + _t("необязательные:", "optional:"))
            for e in sorted_by_dl(b["opt"], b):
                say("    " + block_line(e, b, False, 6))
    say()
    say(GREEN + BOLD + _t("=== Итог: сборки по числу аддонов ===", "=== Total: builds by number of addons ===") + RESET)
    for i, b in enumerate(blocks, 1):
        say(" {}) {}".format(i, block_head(b)))


def write_reports(main, blocks):
    slug = _slug_of(main)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    lines = [_t("Сборки для мода: {} | обновлено {}", "Builds for mod: {} | updated {}").format(main['title'], stamp), ""]
    ai = [f"# build for {main['title']} | {stamp} | M=Modrinth CF=CurseForge x:=exclusive opt=optional addons"]
    for b in blocks:
        lines.append(block_head(b))
        for e in sorted_by_dl(b['req'], b):
            lines.append("  " + block_line(e, b, True, 0))
        if b['opt']:
            lines.append("  " + _t("Необязательные:", "Optional:"))
            for e in sorted_by_dl(b['opt'], b):
                lines.append("    " + block_line(e, b, True, 0))
        if b['elsewhere']:
            lines.append("  " + _t("Нет в этой сборке, но есть на других версиях ({}):", "Not in this build but exist on other versions ({}):").format(len(b['elsewhere'])))
            for e, w in sorted(b['elsewhere'], key=lambda x: x[0]['title'].lower()):
                lines.append(f"    {e['title']} ({', '.join(w)})")
        lines.append("")

        def names(lst):
            out = []
            for e in sorted_by_dl(lst, b):
                t = "+".join({'M': "M", 'CF': "CF"}[x] for x in sorted(e['pmap'].get(b['key'], set()), reverse=True))
                out.append(("x:" if e['n'] in b['excl'] else "") + e['title'] + "[" + t + "]")
            return "; ".join(out)
        row = f"{b['key'][0]} {b['key'][1]} n={len(b['req'])}: {names(b['req'])}"
        if b['opt']:
            row += " | opt: " + names(b['opt'])
        ai.append(row)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    paths = (os.path.join(OUTPUT_DIR, "build_{}.txt".format(slug)), os.path.join(OUTPUT_DIR, "build_{}_ai.txt".format(slug)))
    for path, text in zip(paths, ("\n".join(lines), "\n".join(ai))):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return paths

#F44

def mr_pick(pid, loader, ver):
    key = f"mr_pick_v2k:{pid}:{loader}:{ver}"
    cached = cache_get(key)
    if cached != "MISS":
        return cached
    url = ("https://api.modrinth.com/v2/project/{}/version?loaders={}&game_versions={}").format(
        pid, urllib.parse.quote(json.dumps([loader])), urllib.parse.quote(json.dumps([ver])))
    data = http_get_json(url)
    if not isinstance(data, list):
        return None
    vs = [v for v in data if isinstance(v, dict) and v.get("files")]
    vs.sort(key=lambda v: v.get("date_published") or "", reverse=True)
    vs.sort(key=lambda v: {"release": 0, "beta": 1, "alpha": 2}.get(v.get("version_type"), 3))
    result = None
    if vs:
        v = vs[0]
        f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
        result = {"url": f.get("url"), "filename": f.get("filename"), "vtype": v.get("version_type") or "?",
                  "host": "modrinth", "sha1": (f.get("hashes") or {}).get("sha1"),
                  "sha512": (f.get("hashes") or {}).get("sha512"), "size": f.get("size"),
                  "version": v.get("version_number") or v.get("name") or "?",
                  "deps": [[d.get("dependency_type"), d.get("project_id")] for d in (v.get("dependencies") or [])
                           if d.get("project_id")]}
    cache_set(key, result)
    return result

def cf_pick(mid, loader, ver, api_key):
    key = f"cf_pick_v2y:{mid}:{loader}:{ver}"
    cached=cache_get(key)
    if cached != "MISS":
        return cached
    base = f"https://api.curseforge.com/v1/mods/{mid}/files?gameVersion={urllib.parse.quote(ver)}&pageSize=50"
    data = http_get_json(base + f"&modLoaderType={CF_LOADER_IDS[loader]}", headers=cf_headers(api_key))
    if data == None:
        return None
    files=data.get("data") or []
    if not files and loader == "forge" and _vtup(ver) < (1, 14, 0):
        files = (http_get_json(base, headers=cf_headers(api_key)) or {}).get("data") or []
    files = [f for f in files if isinstance(f, dict) and f.get("isAvailable", True)]
    files.sort(key=lambda f: f.get("fileDate") or "", reverse=True)
    files.sort(key=lambda f: f.get("releaseType") or 9)
    result = None
    if files:
        f = files[0]
        result = {"url": f.get("downloadUrl"), "filename": f.get("fileName"),
                  "vtype": {1: "release", 2: "beta", 3: "alpha"}.get(f.get("releaseType"), "?"),
                  "version": f.get("displayName") or f.get("fileName") or "?",
                  "deps": [[CF_RELATION_TYPE.get(d.get("relationType"), "embedded"), d.get("modId")]
                           for d in (f.get("dependencies") or []) if d.get("modId")]}
        result["host"] = "curseforge"
        result["sha1"] = cf_file_sha1(f)
        if not result["url"] and HASH_MATCH:
            via_modrinth(result)
    cache_set(key, result)
    return result


def pick_file(side, tid, loader, ver, api_key):
    return mr_pick(tid, loader, ver) if side == "mr" else cf_pick(tid, loader, ver, api_key)

def dep_card(side, tid, api_key):
    if side == "mr":
        p = mr_by_slug(tid)
        return card_from_mr_project(p) if p else None
    m = cf_mod_by_id(tid, api_key) if api_key else None
    return normalize_cf_hit(m) if m else None

def ent_links(ent):
    return [ent[s]["card"]["link"] for s in ("mr", "cf") if ent.get(s) and ent[s]["card"].get("link")]

def resolve_items(W, sel, loader, ver, api_key):
    items, missing, libs, req_by = [], [], [], {}
    lock = threading.Lock()
    sel_n = set(e['n'] for e in sel)
    done_titles = set(norm_title(e['title']) for e in sel) 

    def want_libs(pick, side, who):
        for kind, tid in pick.get('deps', []):
            if kind != "required" or not tid:
                continue
            ent = W["by_" + side].get(tid)
            if ent is not None and ent['n'] in sel_n:
                continue
            libs.append((side, tid, who))

    def one(e):
        tags = e['pmap'].get((loader, ver), set())
        pick, used = None, None
        for s, t in (("mr", "M"), ("cf", "CF")):
            if not e.get(s) or t not in tags:
                continue
            p = pick_file(s, e[s]['id'], loader, ver, api_key)
            if p and (p.get('url') or pick is None):
                pick, used = p, s
                if p.get('url'):
                    break
        with lock:
            if not pick:
                missing.append({'title': e['title'], 'links': ent_links(e), 'who': ""})
                return
            items.append({'title': e['title'], 'side': used, 'id': e[used]['id'], 'pick': pick, 'ents': e, 'lib': False})
            want_libs(pick, used, e['title'])

    def one_lib(x):
        side, tid, who = x
        card = dep_card(side, tid, api_key)
        if card is None:
            with lock:
                missing.append({'title': f"{side}:{tid}", 'links': [], 'who': who})
            return
        nt = norm_title(card.get('title'))
        with lock:
            req_by.setdefault(nt, set()).add(who)
            if nt in done_titles:
                return
            done_titles.add(nt)
        pick, used, ucard = pick_file(side, tid, loader, ver, api_key), side, card
        if not pick or not pick.get('url'):
            other = None
            if card['source'] == "Modrinth" and api_key:
                hit = other_on_cf(card, api_key)
                other = normalize_cf_hit(hit) if hit else None
            elif card['source'] != "Modrinth":
                other = other_on_mr(card)
            if other:
                s2 = "mr" if other['source'] == "Modrinth" else "cf"
                p2 = pick_file(s2, other['id'], loader, ver, api_key)
                if p2 and (p2.get('url') or not pick):
                    pick, used, ucard = p2, s2, other
        with lock:
            if not pick:
                missing.append({'title': card.get('title') or "?", 'links': [card.get('link')], 'who': who})
                return
            items.append({'title': ucard.get('title') or "?", 'side': used, 'id': ucard['id'], 'pick': pick,
                          'ents': None, 'lib': True, 'who': who, 'whos': req_by[nt]})
            want_libs(pick, used, ucard.get('title') or "?")

    _parallel_map(one, sel)
    seen_lib, level = set(), 0
    while libs and level < 8:
        level += 1
        batch, libs = libs, []
        batch = [x for x in batch if (x[0], x[1]) not in seen_lib]
        seen_lib.update((x[0], x[1]) for x in batch)
        _parallel_map(one_lib, batch)
    return items, missing

def ask_conflicts(items):
    idx={}
    for it in items:
        idx[(it['side'], it['id'])] = it
        if it.get('ents'):
            for s in ("mr", "cf"):
                if it['ents'].get(s):
                    idx[(s, it['ents'][s]['id'])] = it
    pairs, seen = [], set()
    for it in items:
        for kind, tid in it['pick'].get('deps', []):
            other = idx.get((it['side'], tid)) if kind == "incompatible" else None
            if other is not None and other is not it and frozenset((id(it), id(other))) not in seen:
                seen.add(frozenset((id(it), id(other))))
                pairs.append((it, other))
    alive = set(id(x) for x in items)
    for a, b in pairs:
        if id(a) not in alive or id(b) not in alive:
            continue
        say(YELLOW + _t("Конфликт: '{}' и '{}' объявлены несовместимыми.", "Conflict: '{}' and '{}' are marked incompatible.").format(a['title'], b['title']) + RESET)
        ans = _ask(_t("    Убрать: 1 = {}, 2 = {}, Enter = оставить оба: ", "  Remove: 1 = {}, 2 = {}, Enter keeps both: ").format(a['title'], b['title']))
        victim = a if ans == "1" else b if ans == "2" else None
        if victim is None:
            continue
        if victim.get('ents') is not None and victim['ents'].get('main'):
            say("  " + _t("Главный мод убирать нельзя.", "Can't remove the main mod."))
            continue
        alive.discard(id(victim))
    changed = len(alive) < len(items)
    while changed:      #F45
        changed = False
        names = set(x['title'] for x in items if id(x) in alive)
        for x in items:
            if id(x) in alive and x['lib'] and not (x['whos'] & names):
                alive.discard(id(x))
                changed = True
    return [x for x in items if id(x) in alive]


def _fname(it):
    fn = re.sub(r'[\\/:*?"<>|]+', "_", os.path.basename(it['pick'].get('filename') or "")).strip()
    return fn or (re.sub(r"[^A-Za-z0-9._-]+", "_", it['title']) + ".jar")

#F69

def fmt_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%d%s" % (n, u)
        n //= 1024
    return "%dTB" % n


def http_download(url, dest):
    tmp = dest + ".part"
    for attempt in range(3):
        if _CANCEL.is_set():
            break
        try:
            req = urllib.request.Request(url, headers={'User-Agent': "mod-finder-script"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
            os.replace(tmp, dest)
            return True
        except Exception:
            time.sleep(1 + attempt)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return False

def download_all(items, mods_dir):
    ok, bad, manual, todo = [], [], [], []
    for it in items:
        if it["pick"].get("url"):
            todo.append((it, os.path.join(mods_dir, _fname(it))))
        else:
            manual.append(it)
    lock = threading.Lock()
    prog = {"n": 0}

    def one(x):
        it, dest = x
        good = (os.path.exists(dest) and os.path.getsize(dest) > 0) or http_download(it["pick"]["url"], dest)
        with lock:
            (ok if good else bad).append(it)
            prog["n"] += 1
            if prog["n"] % 10 == 0:
                say(_t("  скачано {}/{}", "  downloaded {}/{}").format(prog["n"], len(todo)))

    _parallel_map(one, todo, workers=DL_WORKERS)
    return ok, bad, manual

def item_links(it):
    if it.get("ents"):
        return ent_links(it["ents"])
    return [it.get("link")] if it.get("link") else []

def make_pack(W, b, api_key):
    main = W["ents"][0]
    loader, ver = b["key"]
    sel = [main] + list(b["req"])
    say()
    say(_t("Собираю список файлов для {} {}, модов в сборке {}...", "Collecting files for {} {} (mods in the build: {})...").format(LOADER_LABEL[loader], ver, len(sel)))
    folder = os.path.join(PACKS_DIR, "{}_{}_{}".format(_slug_of(main), loader, ver))
    mods_dir = os.path.join(folder, "mods")
    try:
        items, missing = resolve_items(W, sel, loader, ver, api_key)
        items = ask_conflicts(items)
        os.makedirs(mods_dir, exist_ok=True)
        say(_t("Скачиваю {} файл(ов) в {} ...", "Downloading {} file(s) to {} ...").format(
            sum(1 for it in items if it["pick"].get("url")), mods_dir))
        ok, bad, manual = download_all(items, mods_dir)
    except KeyboardInterrupt:
        _CANCEL.clear()
        say(f"{YELLOW}{_t('Прервано, модпак не завершён.', 'Interrupted, modpack is not finished.')}{RESET}")
        return
    lines = [_t("Модпак: {} | {} {} | {}", "Modpack: {} | {} {} | {}").format(
        main["title"], LOADER_LABEL[loader], ver, time.strftime("%Y-%m-%d %H:%M")), ""]
    lines.append(_t("Скачано ({}):", "Downloaded ({}):").format(len(ok)))
    for it in sorted(ok, key=lambda x: x["title"].lower()):
        lines.append("  {} | {} | {} | {}{}{}".format(
            it["title"], "Modrinth" if (it["side"] == "mr" or it["pick"].get("via")) else "CurseForge", it["pick"].get("version"),
            _fname(it), "" if it["pick"].get("vtype") == "release" else " | " + str(it["pick"].get("vtype")),
            _t(" | библиотека для: ", " | library for: ") + it.get("who", "") if it["lib"] else ""))
    problems = []
    for title, lst in ((_t("Скачать вручную (автор запретил автоскачивание)", "Download manually (author disabled it)"), manual),
                       (_t("Не удалось скачать", "Download failed"), bad)):
        if lst:
            problems.append((title, [(it["title"], item_links(it)) for it in lst]))
    if missing:
        problems.append((_t("Нет файла под эту версию/загрузчик", "No file for this version/loader"),
                         [(m["title"] + (" (" + m["who"] + ")" if m.get("who") else ""), m["links"]) for m in missing]))
    for title, lst in problems:
        lines.append("")
        lines.append(f"{title} ({len(lst)}):")
        for name, links in lst:
            lines.append(f"  {name}  {' | '.join(x for x in links if x)}")
    with open(os.path.join(folder, "modpack.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    say(GREEN + BOLD + _t("Готово: скачано {} из {}, библиотек среди них {}.", "Done: {} of {} downloaded (libraries: {}).").format(
        len(ok), len(ok) + len(bad), sum(1 for it in ok if it["lib"])) + RESET)
    for title, lst in problems:
        say(YELLOW + "{} ({}):".format(title, len(lst)) + RESET)
        for name, links in lst:
            say("  {}  {}".format(name, " | ".join(x for x in links if x)))
    say(_t("Папка: {}  (список: modpack.txt)", "Folder: {}  (list: modpack.txt)").format(folder))
    after_pack(main, loader, ver, ok, mods_dir, folder)



#F46

def parse_build_args(args):
    opts = {"target": None, "loaders": [], "versions": [], "mr": 0, "cf": 0}
    rest = []
    for a in args:
        low = {"neo": "neoforge"}.get(a.lower(), a.lower())
        m = re.match(r"^(mr|cf)=(\d+)([km]?)$", low)
        if m:
            opts[m.group(1)] = int(m.group(2)) * {"": 1, "k": 1000, "m": 1000000}[m.group(3)]
        elif low in LOADERS:
            if low not in opts["loaders"]:
                opts["loaders"].append(low)
        elif REL_VER_RE.match(a):
            opts["versions"].append(a)
        else:
            rest.append(a)
    opts["target"] = rest[0] if rest else args[0]
    for a in rest[1:]:
        say(YELLOW + _t("Неизвестный параметр '{}', пропускаю.", "Don't know option '{}', skipping.").format(a) + RESET)
    return opts


def do_build(args, api_key):
    tr = T[LANG]
    if not args:
        say(_t("Использование: build <ссылка|slug> [forge|neoforge|fabric|quilt] [версия ...] [mr=N] [cf=N]",
                "Usage: build <link|slug> [forge|neoforge|fabric|quilt] [version ...] [mr=N] [cf=N]"))
        return
    if not check_internet():
        say(f"{RED}{tr['no_internet']}{RESET}")
        return
    _CANCEL.clear()
    opts = parse_build_args(args)
    if not api_key:
        say(f"{YELLOW}{tr['search_cf_skipped']}{RESET}")
    say(_t("Ищу главный мод...", "Looking for the main mod..."))
    mr_card, cf_slim = find_main_mod(opts['target'], api_key)
    if not mr_card and not cf_slim:
        say(f"{RED}{T[LANG]['mod_not_found']}{RESET}")
        return
    title = (mr_card or normalize_cf_hit(cf_slim))['title']
    W = new_world(title, mr_record(mr_card) if mr_card else None,
                         cf_record(cf_slim, api_key, with_deps=False) if cf_slim else None)
    say(_t("Главный мод: {} ({}).", "Main mod: {} ({}).").format(
        title, " + ".join(n for n, c in (("Modrinth", mr_card), ("CurseForge", cf_slim)) if c)))
    if len(_blob(_qname(title))) < 3:
        say(YELLOW + _t("Название короткое, поэтому по нему найдутся не все аддоны.", "Name is short, not all addons will be found by it.") + RESET)
    try:
        analyze_world(W, api_key, opts, _blob(_qname(title)))
        ask_possible(W, opts, api_key)
    except KeyboardInterrupt:
        say()
        say(f"{YELLOW}{tr['bulk_interrupted']}{RESET}")
    _CANCEL.clear()
    save_cache()
    aggregate(W)
    blocks = make_blocks(W, opts)
    if not blocks:
        say(_t("У главного мода нет версий под выбранные загрузчики/версии.", "Main mod has no versions for the chosen loaders/versions."))
        return
    print_blocks(W['ents'][0], blocks)
    try:
        paths = write_reports(W['ents'][0], blocks)
        say(_t("Отчёты: {} (для чтения), {} (сжато, для нейронки)", "Reports: {} (to read), {} (compact, for LLM)").format(
            os.path.relpath(paths[0], SCRIPT_DIR), os.path.relpath(paths[1], SCRIPT_DIR)))
    except OSError as e:
        say(tr['save_error'].format(err=e))
    while True:
        ans = _ask(_t("Создать модпак? Номер сборки из списка (Enter = нет): ", "Make a modpack? Build number from the list (Enter = no): "))
        if not ans or not ans.isdigit() or not (1 <= int(ans) <= len(blocks)):
            break
        make_pack(W, blocks[int(ans) - 1], api_key)
        save_cache()
    say(tr['commands'])


HASH_MATCH = True     #F47
AUTO_MRPACK = True    #F48
LOADER_DEP = {"forge": "forge", "neoforge": "neoforge", "fabric": "fabric-loader", "quilt": "quilt-loader"}


def cf_file_sha1(f):
    for h in f.get("hashes") or []:
        if h.get("algo") == 1 and h.get("value"):
            return str(h["value"]).lower()
    return None


def cf_sha1s(hit):
    out = []
    for f in (hit.get('latestFiles') or [])[:20]:
        s = cf_file_sha1(f)
        if s and s not in out:
            out.append(s)
    return out

def http_post_json(url, body, extra=None):
    host = urllib.parse.urlparse(url).netloc
    data = json.dumps(body).encode("utf-8")
    for attempt in range(3):
        if _CANCEL.is_set():
            return None
        with _HTTP_LOCK:
            wait = 0.22 - (time.time() - _LAST_REQ.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            _LAST_REQ[host] = time.time()
        try:
            req = urllib.request.Request(url, data=data, method="POST",
                                         headers=dict({"User-Agent": "mod-finder-script", "Content-Type": "application/json"}, **(extra or {})))
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                _CANCEL.wait(2 ** (attempt + 1))
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            time.sleep(1 + attempt)
    return None

def mr_hash_lookup(hashes):
    out, need = {}, []
    for h in hashes or []:
        cached = cache_get("mr_hash_v1c:" + h)
        if cached == "MISS":
            need.append(h)
        elif cached:
            out[h] = cached
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        data = http_post_json("https://api.modrinth.com/v2/version_files", {'hashes': chunk, 'algorithm': "sha1"})
        if not isinstance(data, dict):
            continue
        for h in chunk:
            v, info = data.get(h), None
            if isinstance(v, dict) and v.get('project_id'):
                f = next((x for x in (v.get('files') or []) if str((x.get('hashes') or {}).get('sha1')).lower() == h), None)
                if f:
                    info = {'pid': v['project_id'], 'url': f.get('url'), 'filename': f.get('filename'), 'sha1': h,
                            'sha512': (f.get('hashes') or {}).get('sha512'), 'size': f.get('size')}
            cache_set("mr_hash_v1c:" + h, info)
            if info:
                out[h] = info
    return out


def mr_for_cf(card, hashes):
    if HASH_MATCH and hashes:
        pids = [i['pid'] for i in mr_hash_lookup(hashes).values()]
        if pids:
            p = mr_by_slug(max(set(pids), key=pids.count))
            if p and p.get('project_type') in (None, "mod"):
                return card_from_mr_project(p)
    return other_on_mr(card)

def via_modrinth(res):
    sha1 = res.get("sha1")
    info = mr_hash_lookup([sha1]).get(sha1) if sha1 else None
    if info and info.get("url"):
        res.update({"url": info["url"], "filename": info.get("filename") or res.get("filename"), "host": "modrinth",
                    "sha1": info["sha1"], "sha512": info.get("sha512"), "size": info.get("size"), "via": "modrinth"})


def loader_version(loader, mc):
    key = "loader_ver_v1:{}:{}".format(loader, mc)
    cached = cache_get(key, ttl=24 * 3600)
    if cached != "MISS" and cached:
        return cached
    ver = None
    if loader in ("fabric", "quilt"):
        base = "https://meta.fabricmc.net/v2" if loader == "fabric" else "https://meta.quiltmc.org/v3"
        data = http_get_json(f"{base}/versions/loader/{urllib.parse.quote(mc)}")
        vs = []
        if isinstance(data, list):
            vs = [x["loader"]["version"] for x in data if isinstance(x, dict) and (x.get("loader") or {}).get("version")]
        ver = next((v for v in vs if "beta" not in v and "pre" not in v), vs[0] if vs else None)
    elif loader == "forge":
        data = http_get_json("https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json")
        promos = (data or {}).get("promos") or {}
        ver = promos.get(mc + "-recommended") or promos.get(mc + "-latest")
    elif loader == "neoforge":
        data = http_get_json("https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge")
        parts = mc.split(".")
        if _vtup(mc)[0] >= 26:      #F49
            prefix = ".".join((parts + ["0", "0"])[:3]) + "."
        else:                           #F50
            prefix = ".".join((parts[1:] + ["0"])[:2]) + "."
        vs = [v for v in ((data or {}).get("versions") or []) if str(v).startswith(prefix)]
        pool = [v for v in vs if "-" not in v] or vs
        ver = max(pool, key=lambda v: tuple(int(x) for x in re.findall(r"\d+", v))) if pool else None
    if ver:
        cache_set(key, ver)
    return ver

def export_mrpack(main, loader, ver, ok, mods_dir, folder):
    seen2 = set()
    lv = loader_version(loader, ver)
    if not lv:
        lv = _ask(_t("Не удалось определить версию {} для Minecraft {}. Введите вручную (Enter = пропустить .mrpack): ", "Can't detect the {} version for Minecraft {}. Type it manually (Enter = skip .mrpack): ").format(
                                LOADER_LABEL[loader], ver))
    if not lv:
        say(_t(".mrpack пропущен.", ".mrpack skipped."))
        return None
    files, bundled = [], []
    for it in sorted(ok, key=lambda x: x['title'].lower()):
        p, fn = it['pick'], _fname(it)
        if p.get('host') == "modrinth" and p.get('sha1') and p.get('sha512') and p.get('size') and p.get('url'):
            files.append({'path': "mods/" + fn, 'hashes': {'sha1': p['sha1'], 'sha512': p['sha512']},
                          'downloads': [p['url']], 'fileSize': p['size']})
        elif os.path.isfile(os.path.join(mods_dir, fn)):
            bundled.append(fn)
    index = {'formatVersion': 1, 'game': "minecraft", 'versionId': time.strftime("%Y.%m.%d.%H%M"),
             'name': "{} ({} {})".format(main['title'], LOADER_LABEL[loader], ver),
             'summary': _t("Собрано автоматически: главный мод + аддоны + библиотеки",
                            "Built automatically: main mod + addons + libraries"),
             'files': files, 'dependencies': {'minecraft': ver, LOADER_DEP[loader]: lv}}
    path = os.path.join(folder, "{}_{}_{}.mrpack".format(_slug_of(main), loader, ver))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("modrinth.index.json", json.dumps(index, ensure_ascii=False, indent=2))
        for fn in bundled:
            z.write(os.path.join(mods_dir, fn), "overrides/mods/" + fn)
    say(GREEN + BOLD + _t(".mrpack готов: {}", ".mrpack ready: {}").format(path) + RESET)
    say(_t("  загрузчик {} {}; по ссылкам Modrinth: {}, внутри архива (overrides/mods): {}",
            "  loader {} {}; by Modrinth links: {}, inside the archive (overrides/mods): {}").format(
                LOADER_LABEL[loader], lv, len(files), len(bundled)))
    return path


def after_pack(main, loader, ver, ok, mods_dir, folder):
    via = [it["title"] for it in ok if it["pick"].get("via")]
    if via:
        say(YELLOW + _t("С Modrinth по хешу взяты файлы, которые не скачать с CurseForge ({}): {}", "Took from Modrinth by hash what CurseForge does not allow to download ({}): {}").format(
                             len(via), ", ".join(via)) + RESET)
        try:
            with open(os.path.join(folder, "modpack.txt"), "a", encoding="utf-8") as f:
                f.write("\n" + _t("С Modrinth по хешу файла CurseForge ({}): {}",
                                   "From Modrinth by CurseForge file hash ({}): {}").format(len(via), ", ".join(via)) + "\n")
        except OSError:
            pass
    if AUTO_MRPACK and ok:
        try:
            export_mrpack(main, loader, ver, ok, mods_dir, folder)
        except KeyboardInterrupt:
            _CANCEL.clear()
            say(f"{YELLOW}{_t('Прервано, .mrpack не создан.', 'Interrupted, .mrpack not created.')}" + RESET)
        except Exception as e:
            say(YELLOW + _t(".mrpack не создан: {}", ".mrpack not created: {}").format(e) + RESET)


SETTINGS_PATH = os.path.join(SCRIPT_DIR, ".importlink_settings.json")  #F8
MANIFEST_NAME = ".importlink.json"     #F51
IMPORT_WORKERS = 4                       #F52
READY_LINES = 8                   #F53
BAR_WIDTH = 24
FILES_CACHE_TTL = 3600                  #F54
SETTINGS_DEFAULTS = {"version": "", "loader": "", "prefer": "auto", "strict": False, "min_mr": 0, "min_cf": 0, "deps": True, "releases": False}
_NUM_RE = re.compile(r"\d+(?:\.\d+)*")
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_REL_RANK = {"release": 0, "beta": 1, "alpha": 2}


#F55


def load_settings():
    s = dict(SETTINGS_DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            s.update(dict((k, d[k]) for k in SETTINGS_DEFAULTS if k in d))
    except (OSError, ValueError):
        pass
    return s



def save_settings(s):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False)
    except OSError:
        pass


def show_settings(s):
    return _t("версия {} | загрузчик {} | prefer {}{} | min mr={} cf={} | зависимости {}",
               "version {} | loader {} | prefer {}{} | min mr={} cf={} | dependencies {}").format(
        s['version'] or "?", s['loader'] or "?", s['prefer'], "!" if s['strict'] else "", s['min_mr'], s['min_cf'],
        _t("да", "on") if s['deps'] else _t("нет", "off")) + (_t(" | только релизы", " | only releases") if s.get('releases') else "")


def parse_opts(tokens, s):
    toks = [t for t in tokens if t]
    i=0
    while i < len(toks):
        t, nxt = toks[i].lower(), (toks[i + 1] if i + 1 < len(toks) else "")
        m = re.match(r"^(mr|cf)=(\d+)([km]?)$", t)
        if t == "prefer" and nxt:
            s['strict'] = nxt.endswith("!")
            s['prefer'] = {'m': "M", 'mr': "M", 'modrinth': "M", 'cf': "CF", 'curseforge': "CF"}.get(nxt.lower().rstrip("!"), "auto")
            i += 2
        elif t == "min" and nxt.lower() in ("off", "none", "0"):
            s['min_mr'] = s['min_cf'] = 0
            i += 2
        elif m:
            s["min_" + m.group(1)] = int(m.group(2)) * {"": 1, 'k': 1000, 'm': 1000000}[m.group(3)]
            i += 1
        elif t == "version" and nxt:
            s['version'] = nxt
            i += 2
        elif t == "loader" and nxt:
            s['loader'] = {'neo': "neoforge"}.get(nxt.lower(), nxt.lower())
            i += 2
        elif t == "deps" and nxt:
            s['deps'] = nxt.lower() not in ("off", "no", "n", "0")
            i += 2
        elif t == "only" and nxt.lower().startswith("release"):
            s['releases'] = True
            i += 2
        elif t == "only" and nxt.lower() in ("off", "no", "any", "all"):
            s['releases'] = False
            i += 2
        elif t in ("releases", "release"):
            off = nxt.lower() in ("off", "no", "n", "0")
            s['releases'] = not off
            i += 2 if (off or nxt.lower() in ("on", "yes", "y", "1")) else 1
        elif REL_VER_RE.match(toks[i]):
            s['version'] = toks[i]
            i += 1
        elif t in LOADERS or t == "neo":
            s['loader'] = {'neo': "neoforge"}.get(t, t)
            i += 1
        else:
            i += 1

#F56

def mc_tuple(mc, *names):
    for s in names:
        s = re.sub(r"(?i)\.(jar|zip)$", "", str(s or ""))
        if mc:
            s = s.replace(mc, " ")
        s = re.sub(r"(?i)neoforge|forge|fabric|quilt|minecraft|mc", " ", s)
        best = None
        for t in _NUM_RE.findall(s):
            if best is None or len(t.split(".")) >= len(best.split(".")):
                best = t
        if best:
            return tuple(int(x) for x in best.split("."))
    return ()


def _pad3(vt):
    return (tuple(vt) + (0,) * 8)[:8]       #F57

def _cand_key(c):
    return (_pad3(c['vt']), c['date'])

def _ver_disp(c):
    return ".".join(str(x) for x in c["vt"]) if c["vt"] else str(c["vname"])


def mr_cands(pid, loader, ver, only_rel=False):
    key = f"il_mr_v2:{pid}:{loader}:{ver}:{int(only_rel)}"
    cached = cache_get(key, ttl=FILES_CACHE_TTL)
    if cached != "MISS":
        return cached
    url = "https://api.modrinth.com/v2/project/{}/version?loaders={}&game_versions={}".format(
        pid, urllib.parse.quote(json.dumps([loader])), urllib.parse.quote(json.dumps([ver])))
    data = http_get_json(url)
    if not isinstance(data, list):
        return None
    best = None
    for v in data:
        files = (v.get('files') or []) if isinstance(v, dict) else []
        if not files:
            continue
        if only_rel and v.get('version_type') != "release":
            continue
        f = next((x for x in files if x.get('primary')), files[0])
        hs = f.get('hashes') or {}
        c = {'src': "M", 'pid': pid, 'vt': mc_tuple(ver, v.get('version_number'), f.get('filename')),
             'vname': v.get('version_number') or v.get('name') or "?", 'rank': _REL_RANK.get(v.get('version_type'), 3),
             'vtype': v.get('version_type') or "?", 'date': v.get('date_published') or "", 'filename': f.get('filename'),
             'url': f.get('url'), 'sha1': hs.get('sha1'), 'sha512': hs.get('sha512'), 'size': f.get('size'),
             'host': "modrinth",
             'deps': [[d.get('dependency_type'), d.get('project_id')] for d in (v.get('dependencies') or [])
                      if d.get('project_id')]}
        if best is None or _cand_key(c) > _cand_key(best):
            best = c
    cache_set(key, best)
    return best

def cf_cands(mid, loader, ver, api_key, only_rel=False):
    key = f"il_cf_v2:{mid}:{loader}:{ver}:{int(only_rel)}"
    cached = cache_get(key, ttl=FILES_CACHE_TTL)
    if cached != "MISS":
        return cached
    base = "https://api.curseforge.com/v1/mods/{}/files?gameVersion={}&pageSize=50".format(mid, urllib.parse.quote(ver))
    data = http_get_json(base + f"&modLoaderType={CF_LOADER_IDS[loader]}", headers=cf_headers(api_key))
    if data == None:
        return None
    files = data.get("data") or []
    if not files and loader == "forge" and _vtup(ver) < (1, 14, 0):
        files = (http_get_json(base, headers=cf_headers(api_key)) or {}).get("data") or []
    best = None
    for f in files:
        if not isinstance(f, dict) or not f.get("isAvailable", True):
            continue
        rel = {1: "release", 2: "beta", 3: "alpha"}.get(f.get("releaseType"), "?")
        if only_rel and rel != "release":
            continue
        c = {"src": "CF", "pid": mid, "vt": mc_tuple(ver, f.get("displayName"), f.get("fileName")),
             "vname": f.get("displayName") or f.get("fileName") or "?", "rank": _REL_RANK.get(rel, 3), "vtype": rel,
             "date": f.get("fileDate") or "", "filename": f.get("fileName"), "url": f.get("downloadUrl"),
             "sha1": cf_file_sha1(f), "sha512": None, "size": f.get("fileLength"), "host": "curseforge",
             "deps": [[CF_RELATION_TYPE.get(d.get("relationType"), "embedded"), d.get("modId")]
                      for d in (f.get("dependencies") or []) if d.get("modId")]}
        if best is None or _cand_key(c) > _cand_key(best):
            best = c
    if best is not None and not best["url"] and HASH_MATCH:
        via_modrinth(best)       #F58
    cache_set(key, best)
    return best #FTEMPIMPORTANT3

def choose_cand(cands, s):
    cands = [c for c in cands if c]
    if not cands:
        return None
    pref = {"M": "M", "CF": "CF"}.get(s["prefer"])
    usable = [c for c in cands if c.get("url")] or cands
    if pref and s.get("strict"):
        usable = [c for c in usable if c["src"] == pref] or usable
    top_key = max(_pad3(c["vt"]) for c in usable)
    top = [c for c in usable if _pad3(c["vt"]) == top_key]
    if len(top) > 1:
        low = min(c["rank"] for c in top)
        top = [c for c in top if c["rank"] == low]
    if len(top) > 1:
        for c in top:
            if c["src"] == pref:
                return c
        top.sort(key=lambda c: (c["date"], c["src"] == "M"), reverse=True)
    return top[0]


#F59

def extract_urls(lines):
    out = []
    for ln in lines:
        for u in _URL_RE.findall(ln):
            u = u.rstrip(").,;")
            if u not in out:
                out.append(u)
    return out


def unit_from_url(url, api_key):
    pu = urllib.parse.urlparse(url)
    host = pu.netloc.lower()
    parts = [p for p in pu.path.split("/") if p]
    mr_card = cf_slim = None
    if "modrinth.com" in host:
        if len(parts) < 2 or parts[0] not in ("mod", "project"):
            return None, _t("это не ссылка на мод Modrinth", "not a Modrinth mod link")
        p = mr_by_slug(parts[1])
        if not p or p.get('project_type') not in (None, "mod"):
            return None, _t("не мод или не найден на Modrinth", "not a mod / not found on Modrinth")
        mr_card = card_from_mr_project(p)
    elif "curseforge.com" in host:
        if not api_key:
            return None, _t("для ссылок CurseForge нужен API-ключ (команда key)", "CurseForge links need an API key (key command)")
        if len(parts) >= 3 and parts[:2] == ["minecraft", "mc-mods"]:
            cf_slim = cf_by_slug(parts[2], api_key)
        elif len(parts) >= 2 and parts[0] == "projects" and parts[1].isdigit():
            raw = cf_mod_by_id(parts[1], api_key)
            cf_slim = slim_cf_hit(raw) if raw and raw.get('classId') in (None, CF_CLASS_ID_MODS) else None
        else:
            return None, _t("это не ссылка на мод CurseForge", "not a CurseForge mod link")
        if not cf_slim:
            return None, _t("мод не найден на CurseForge", "mod not found on CurseForge")
    else:
        return None, _t("ссылка не с Modrinth/CurseForge", "not a Modrinth/CurseForge link")
    return {'mr': mr_card, 'cf': cf_slim, 'title': (mr_card or normalize_cf_hit(cf_slim))['title'], 'url': url}, None

def dep_unit(src, did, api_key):
    if src == "M":
        p = mr_by_slug(did)
        if not p or p.get("project_type") not in (None, "mod"):
            return None
        card = card_from_mr_project(p)
        return {"mr": card, "cf": None, "title": card["title"], "url": card["link"]}
    raw = cf_mod_by_id(did, api_key) if api_key else None
    if not raw or raw.get("classId") not in (None, CF_CLASS_ID_MODS):
        return None
    slim = slim_cf_hit(raw)
    return {"mr": None, "cf": slim, "title": slim["name"], "url": normalize_cf_hit(slim)["link"]}


def find_twin(unit, api_key):
    if unit['mr'] and not unit['cf'] and api_key:
        unit['cf'] = other_on_cf(unit['mr'], api_key)
    elif unit['cf'] and not unit['mr']:
        unit['mr'] = mr_for_cf(normalize_cf_hit(unit['cf']), unit['cf'].get('sha1'))


def unit_ids(unit):
    out = set()
    if unit.get("mr"):
        out.add("mr:" + str(unit["mr"]["id"]))
    if unit.get("cf"):
        out.add("cf:" + str(unit["cf"]["id"]))
    return out

def process_unit(unit, s, api_key):
    jobs, notes = [], []
    if unit["mr"]:
        if (unit["mr"].get("downloads") or 0) >= s["min_mr"]:
            jobs.append(lambda: mr_cands(unit["mr"]["id"], s["loader"], s["version"], s.get("releases", False)))
        else:
            notes.append(_t("Modrinth ниже порога (скачиваний: {})", "Modrinth below the threshold ({} downloads)").format(
                unit["mr"].get("downloads") or 0))
    if unit["cf"] and api_key:
        if (unit["cf"].get("downloadCount") or 0) >= s["min_cf"]:
            jobs.append(lambda: cf_cands(unit["cf"]["id"], s["loader"], s["version"], api_key, s.get("releases", False)))
        else:
            notes.append(_t("CurseForge ниже порога (скачиваний: {})", "CurseForge below the threshold ({} downloads)").format(
                unit["cf"].get("downloadCount") or 0))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        cands = list(ex.map(lambda j: j(), jobs))
    return {"cands": cands, "pick": choose_cand(cands, s), "notes": notes}

#F60

def manifest_load(folder):
    try:
        with open(os.path.join(folder, MANIFEST_NAME), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}

def manifest_save(folder, man):
    try:
        with open(os.path.join(folder, MANIFEST_NAME), "w", encoding="utf-8") as f:
            json.dump(man, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def jar_name(c, title):
    fn = re.sub(r'[\\/:*?"<>|]+', "_", os.path.basename(c.get("filename") or "")).strip()
    return fn or (re.sub(r"[^A-Za-z0-9._-]+", "_", title) + ".jar")

def place_file(unit, c, folder, man, lock):
    fn = jar_name(c, unit['title'])
    dest = os.path.join(folder, fn)
    mid, cid = (unit.get('mr') or {}).get('id'), (unit.get('cf') or {}).get('id')
    old = unit.get('replace')
    if not old:
        with lock:
            for ofn, e in man.items():
                if ofn != fn and ((mid and e.get('mr') == mid) or (cid and e.get('cf') == cid)):
                    old = ofn
    state = "present"
    if not (os.path.isfile(dest) and os.path.getsize(dest) > 0):
        if not http_download(c['url'], dest):
            return "failed"
        state = "new"
    if old and old != fn and os.path.isfile(os.path.join(folder, old)):
        os.makedirs(os.path.join(folder, "_old"), exist_ok=True)
        os.replace(os.path.join(folder, old), os.path.join(folder, "_old", old))
        state = "updated"
    with lock:
        if old:
            man.pop(old, None)
        man[fn] = {'title': unit['title'], 'mr': mid, 'cf': cid, 'src': c['src'], 'version': _ver_disp(c),
                   'sha1': c.get('sha1'), 'date': c.get('date')}
    return state


#F61

class ProgressUI:

    def __init__(self, total):
        self.total, self.done, self.ready = total, 0, []
        self.lock = threading.Lock()
        self.live = sys.stdout.isatty()
        self.h = READY_LINES + 3
        self.drawn = False
        if self.live:
            self.draw()

    def bar(self):
        w = BAR_WIDTH
        f = int(w * self.done / self.total) if self.total else w
        pct = int(100 * self.done / self.total) if self.total else 100
        return "[{}{}] {:3d}%  {}/{}".format("#" * f, "-" * (w - f), pct, self.done, self.total)

    def draw(self):
        cols = shutil.get_terminal_size((100, 20)).columns - 1
        lines = [self.bar(), "", "§ Ready"] + self.ready[-READY_LINES:]
        lines += [""] * (self.h - len(lines))
        sys.stdout.write((f"\033[{self.h}A" if self.drawn else "") + "".join("\r\033[K" + l[:cols] + "\n" for l in lines))
        sys.stdout.flush()
        self.drawn = True

    def tick(self, line=None, grow=0):
        with self.lock:
            self.done += 1
            self.total += grow
            if line:
                self.ready.append(line)
            if self.live:
                self.draw()
            else:
                if line:
                    print("§ Ready " + line)
                if self.done % 10 == 0 or self.done == self.total:
                    print(self.bar())

    def grow(self, n):
        with self.lock:
            self.total += n
            if self.live:
                self.draw()


#F62

def run_units(units, s, folder, api_key, known=None):
    man = manifest_load(folder)
    known = set(known or [])
    for e in man.values():
        if e.get('mr'):
            known.add("mr:" + str(e['mr']))
        if e.get('cf'):
            known.add("cf:" + str(e['cf']))
    lock = threading.Lock()
    seen, problems, stats, deps_next = set(), [], {'new': 0, 'updated': 0, 'present': 0}, []
    ui = ProgressUI(len(units))

    def fail(unit, why):
        with lock:
            problems.append((unit.get('title') or unit.get('url') or "?", why, unit.get('url') or ""))
        ui.tick(None)

    def work(unit):
        if "dep" in unit:                                   #F63
            u = dep_unit(unit['dep'][0], unit['dep'][1], api_key)
            if not u:
                return fail({'title': "{}:{}".format(*unit['dep']), 'url': ""}, _t("зависимость не найдена", "dependency not found"))
            unit = u
            if unit_ids(unit) & known:
                return ui.tick(None)
        elif "title" not in unit:                           #F64
            u, why = unit_from_url(unit['url'], api_key)
            if not u:
                return fail(unit, why)
            unit = u
        find_twin(unit, api_key)
        ids = unit_ids(unit)
        with lock:
            if ids & seen:
                dup = True
            else:
                dup = False
                seen.update(ids)
        if dup:
            return ui.tick(None)
        res = process_unit(unit, s, api_key)
        c = res['pick']
        if not c:
            return fail(unit, res['notes'][0] if res['notes'] else _t("нет файла под {} {}", "no file for {} {}").format(
                LOADER_LABEL[s['loader']], s['version']))
        if not c.get('url'):
            return fail(unit, _t("скачать вручную (автор запретил автоскачивание)", "download manually (forbidden by the author)"))
        st = place_file(unit, c, folder, man, lock)
        if st == "failed":
            return fail(unit, _t("не удалось скачать", "download failed"))
        with lock:
            stats[st] += 1
            if s['deps']:
                deps_next.extend({'dep': (c['src'], d[1]), 'who': unit['title']} for d in c['deps'] if d[0] == "required")
        mark = {'new': "", 'updated': _t("  (обновлён)", " (updated)"), 'present': _t(" (уже есть)", " (already there)")}[st]
        ui.tick("-{} -{}- [{}] ({}){}{}".format(unit['title'], _ver_disp(c), jar_name(c, unit['title']), c['src'], mark,
                                         "" if c['vtype'] in ("release", "?") else " [" + c['vtype'] + "]"))

    def safe(unit):
        try:
            work(unit)
        except Exception as e:
            fail(unit if "title" in unit else {'title': unit.get('url') or str(unit.get('dep')), 'url': ""},
                 _t("ошибка: {}", "error: {}").format(e))

    queue, depth = list(units), 0
    try:
        while queue and depth < 5:
            depth += 1
            deps_next[:] = []
            _parallel_map(safe, queue, workers=IMPORT_WORKERS)
            queue = list(deps_next)
            if queue and s['deps']:
                ui.grow(len(queue))
            else:
                queue = []
    finally:
        manifest_save(folder, man)
        save_cache()
    say()
    say(f"{GREEN}{BOLD}" + _t("Готово: новых {}, обновлено {}, уже было {}, проблем {}.", "Done: new {}, updated {}, already there {}, problems {}.").format(
        stats['new'], stats['updated'], stats['present'], len(problems)) + RESET)
    for title, why, url in problems:
        say(YELLOW + f"  {title} - {why} {url}" + RESET)
    try:
        with open(os.path.join(folder, "importlink_log.txt"), "a", encoding="utf-8") as f:
            f.write(f"== {time.strftime('%Y-%m-%d %H:%M')} | {s['loader']} {s['version']} | {show_settings(s)}\n")
            for line in ui.ready:
                f.write(line + "\n")
            for title, why, url in problems:
                f.write(f"! {title} - {why} {url}\n")
    except OSError:
        pass
    say(_t("Папка: {}", "Folder: {}").format(folder))
    return stats, problems

#F65

def pending_input(wait=0.3):
    #F72
    out = []
    try:
        import select
        while sys.stdin.isatty() and select.select([sys.stdin], [], [], wait)[0]:
            ln = sys.stdin.readline()
            if not ln:
                break
            out.append(ln.rstrip("\r\n"))
            wait = 0.15
    except (ImportError, OSError, ValueError):
        pass
    return out


def block_input(prompt):
    first = _ask(prompt)
    if first is None:
        return None
    return [first] + pending_input(0.3)

def is_yes(ans, default=True):
    a = (ans or "").strip().lower()
    return default if not a else a in ("y", "yes", "д", "да", "1")

def ask_target(s, stash=None):
    stash = [] if stash is None else stash
    while True:
        v = _ask(_t("Версия Minecraft [{}]: ", "Minecraft version [{}]: ").format(s['version'] or "1.20.1"))
        if v is None:
            return False
        if _URL_RE.search(v):
            stash.append(v)
            continue
        v = v or s['version']
        if REL_VER_RE.match(v or ""):
            s['version'] = v
            break
        say(_t("Нужна версия вида 1.20.1", "Need a version like 1.20.1"))
    while True:
        lo = _ask(_t("Загрузчик (forge/fabric/neoforge/quilt) [{}]: ", "Loader (forge/fabric/neoforge/quilt) [{}]: ").format(
            s['loader'] or "forge"))
        if lo is None:
            return False
        if _URL_RE.search(lo):
            stash.append(lo)
            continue
        lo = {'neo': "neoforge"}.get((lo or s['loader']).lower(), (lo or s['loader']).lower())
        if lo in LOADERS:
            s['loader'] = lo
            break
        say(_t("Загрузчик: forge, fabric, neoforge или quilt", "Loader: forge, fabric, neoforge or quilt"))
    save_settings(s)
    return True



def pick_folder(s, create=True):
    base = SCRIPT_DIR
    while True:
        say(_t("Папка для модов:", "Folder for the mods:"))
        if create:
            say(_t("  1) создать новую папку рядом со скриптом", "  1) create a new folder next to the script"))
        say(_t("  2) использовать готовую папку (рядом со скриптом)", "  2) use an existing folder (next to the script)"))
        say(_t("  3) использовать папку скрипта, ничего не создавая", "  3) use the script folder, don't create anything"))
        ch = _ask(_t("Выбор [{}]: ", "Choice [{}]: ").format("1" if create else "2"))
        if ch is None:
            return None
        ch = ch or ("1" if create else "2")
        if ch == "3":
            return base
        if ch == "2":
            subs = sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))
                          and not d.startswith((".", "_")) and d not in ("found_mods", "__pycache__"))
            if not subs:
                say(_t("Готовых папок рядом со скриптом нет.", "No folders next to the script."))
                continue
            for i, d in enumerate(subs, 1):
                say(f"  {i}) {d}")
            n = _ask(_t("Номер или название папки: ", "Folder number or name: "))
            if n is None:
                return None
            if n.isdigit() and 1 <= int(n) <= len(subs):
                return os.path.join(base, subs[int(n) - 1])
            if n and os.path.isdir(os.path.join(base, n)):
                return os.path.join(base, n)
            say(_t("Такой папки нет.", "No such folder."))
            continue
        if ch == "1" and create:
            default = f"mods_{s['loader']}_{s['version']}"
            name = _ask(_t("Название новой папки [{}]: ", "New folder name [{}]: ").format(default))
            if name is None:
                return None
            name = re.sub(r'[\\/:*?"<>|]+', "_", name or default).strip() or default
            path = os.path.join(base, name)
            os.makedirs(path, exist_ok=True)
            return path

def run_batch(urls, s, st, api_key):
    n_mr = sum(1 for u in urls if "modrinth.com" in u.lower())
    n_cf = sum(1 for u in urls if "curseforge.com" in u.lower())
    say(_t("Ссылок: {} (Modrinth {}, CurseForge {}); {} {}; prefer {}{}", "Links: {} (Modrinth {}, CurseForge {}); {} {}; prefer {}{}").format(
        len(urls), n_mr, n_cf, LOADER_LABEL[s["loader"]], s["version"], s["prefer"], "!" if s["strict"] else ""))
    ans = _ask(_t("Установить? y/n [y]: ", "Install? y/n [y]: "))
    if ans is None or not is_yes(ans):
        say(T[LANG]["cancelled"])
        return
    if not st.get("folder"):
        st["folder"] = pick_folder(s)
        if not st["folder"]:
            return
    try:
        run_units([{"url": u} for u in urls], s, st["folder"], api_key)
    except KeyboardInterrupt:
        _CANCEL.clear()
        say()
        say(f"{YELLOW}{T[LANG]['interrupted']}{RESET}")


def link_session(s, api_key, lines, stay):
    ok_n = 0
    say(f"{GREEN}{BOLD}{_t('=== importlink: скачивание по ссылкам Modrinth/CurseForge ===', '=== importlink: download by Modrinth/CurseForge links ===')}{RESET}")
    say(_t("Вставьте ссылки (по одной или списком). Команды: prefer CF|M|auto[!], min mr=N cf=N | min off, only releases | only off, version X, loader Y, deps on|off, folder, settings, exit.",
            "Paste links (one by one or a list). Commands: prefer CF|M|auto[!], min mr=N cf=N | min off, only releases | only off, version X, loader Y, deps on|off, folder, settings, exit."))
    pend = list(lines) + pending_input(0.35)
    stash = []
    if not ask_target(s, stash):
        return
    pend += stash
    st = {"folder": None}
    while True:
        for ln in pend:
            if ln.strip() and not _URL_RE.search(ln):
                w = ln.split()
                if w[0].lower() in ("exit", "back", "q", "quit"):
                    save_settings(s)
                    return
                if w[0].lower() == "folder":
                    st["folder"] = None
                elif w[0].lower() == "settings":
                    say(show_settings(s))
                else:
                    parse_opts(w, s)
                    say(show_settings(s))
        save_settings(s)
        urls = extract_urls(pend)
        if urls:
            run_batch(urls, s, st, api_key)
            if not stay:
                return
        pend = block_input("importlink> ")
        if pend is None or not any(p.strip() for p in pend):
            return


def do_importlink(args, api_key):
    s = load_settings()
    parse_opts(args, s)
    link_session(s, api_key, [], True)

def do_import_urls(line, api_key):
    link_session(load_settings(), api_key, [line], False)


#F66

def murmur2(data):
    #F73
    m = 0x5bd1e995
    data = bytes(b for b in data if b not in (9, 10, 13, 32))
    n = len(data)
    h = (1 ^ n) & 0xFFFFFFFF
    i = 0
    while n >= 4:
        k = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16) | (data[i + 3] << 24)
        k = (k * m) & 0xFFFFFFFF
        k ^= k >> 24
        k = (k * m) & 0xFFFFFFFF
        h = ((h * m) & 0xFFFFFFFF) ^ k
        i += 4
        n -= 4
    if n == 3:
        h ^= data[i + 2] << 16
    if n >= 2:
        h ^= data[i + 1] << 8
    if n >= 1:
        h ^= data[i]
        h = (h * m) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * m) & 0xFFFFFFFF
    h ^= h >> 15
    return h

def identify_mods(paths, folder, api_key):
    man, sha, fp, info = manifest_load(folder), {}, {}, {}
    for p in paths:
        with open(p, "rb") as f:
            data = f.read()
        sha[p], fp[p] = hashlib.sha1(data).hexdigest(), murmur2(data)
        e = man.get(os.path.basename(p))
        if e and e.get("sha1") == sha[p]:
            info[p] = {"mr": e.get("mr"), "cf": e.get("cf"), "vname": e.get("version"), "date": e.get("date") or "", "sha1": sha[p]}
    rest = [p for p in paths if p not in info]
    for i in range(0, len(rest), 100):
        chunk = rest[i:i + 100]
        data = http_post_json("https://api.modrinth.com/v2/version_files", {"hashes": [sha[p] for p in chunk], "algorithm": "sha1"})
        for p in chunk:
            v = data.get(sha[p]) if isinstance(data, dict) else None
            if isinstance(v, dict) and v.get("project_id"):
                info[p] = {"mr": v["project_id"], "cf": None, "vname": v.get("version_number"), "date": v.get("date_published") or "",
                           "sha1": sha[p]}
    rest = [p for p in paths if p not in info]
    if api_key and rest:
        for i in range(0, len(rest), 200):
            chunk = rest[i:i + 200]
            data = http_post_json("https://api.curseforge.com/v1/fingerprints/432", {"fingerprints": [fp[p] for p in chunk]},
                                    cf_headers(api_key))
            by_fp = {}
            for m in ((data or {}).get("data") or {}).get("exactMatches") or []:
                f = m.get("file") or {}
                by_fp[f.get("fileFingerprint")] = (m.get("id"), f)
            for p in chunk:
                if fp[p] in by_fp:
                    mid, f = by_fp[fp[p]]
                    info[p] = {"mr": None, "cf": mid, "vname": f.get("displayName") or f.get("fileName"),
                               "date": f.get("fileDate") or "", "sha1": sha[p]}
    return info


def check_updates(paths, info, s, api_key):
    ui = ProgressUI(len(paths))
    out, lock = [], threading.Lock()

    def one(p):
        try:
            i = info.get(p)
            if not i:
                return ui.tick(None)
            unit = {"mr": None, "cf": None, "title": None, "url": "", "replace": os.path.basename(p)}
            if i.get("mr"):
                pr = mr_by_slug(i["mr"])
                unit["mr"] = card_from_mr_project(pr) if pr else None
            if i.get("cf") and api_key:
                raw = cf_mod_by_id(i["cf"], api_key)
                unit["cf"] = slim_cf_hit(raw) if raw else None
            if not (unit["mr"] or unit["cf"]):
                return ui.tick(None)
            unit["title"] = (unit["mr"] or normalize_cf_hit(unit["cf"]))["title"]
            find_twin(unit, api_key)
            c = process_unit(unit, s, api_key)["pick"]
            if c and c.get("url") and c.get("sha1") != i["sha1"]:
                ivt = mc_tuple(s["version"], i.get("vname"), os.path.basename(p))
                if (ivt and c["vt"] and _pad3(c["vt"]) > _pad3(ivt)) or (not (ivt and c["vt"]) and c["date"] > i["date"] > ""):
                    with lock:
                        out.append({"path": p, "unit": unit, "old": ".".join(map(str, ivt)) or str(i.get("vname") or "?"),
                                    "new": _ver_disp(c) + ("" if c["vtype"] in ("release", "?") else " [" + c["vtype"] + "]"), "src": c["src"]})
            ui.tick("-{}".format(unit["title"]))
        except Exception:
            ui.tick(None)

    _parallel_map(one, paths, workers=IMPORT_WORKERS)
    return sorted(out, key=lambda u: u["unit"]["title"].lower())


def do_update(args, api_key):
    s = load_settings()
    parse_opts(args, s)
    say(f"{GREEN}{BOLD}{_t('=== update: обновление модов в папке ===', '=== update: updating mods in a folder ===')}" + RESET)
    folder = pick_folder(s, create=False)
    if not folder or not ask_target(s):
        return
    paths = sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".jar"))
    if not paths:
        say(_t("В папке нет .jar файлов.", "No .jar files in the folder."))
        return
    if not check_internet():
        say(f"{RED}{T[LANG]['no_internet']}{RESET}")
        return
    _CANCEL.clear()
    try:
        say(_t("Определяю моды ({})...", "Identifying mods ({})...").format(len(paths)))
        info = identify_mods(paths, folder, api_key)
        say(_t("Определено {} из {}. Ищу новые версии для {} {}...", "Identified {} of {}. Looking for newer versions for {} {}...").format(
            len(info), len(paths), LOADER_LABEL[s["loader"]], s["version"]))
        plan = check_updates(paths, info, s, api_key)
        say()
        unknown = [os.path.basename(p) for p in paths if p not in info]
        if unknown:
            say(YELLOW + _t("Не определено (не трогаю): {}", "Not identified (left alone): {}").format(", ".join(unknown)) + RESET)
        if not plan:
            say(f"{GREEN}{_t('Все определённые моды уже новейшие.', 'All identified mods are already the newest.')}{RESET}")
            return
        say(BOLD + _t("Доступны обновления ({}):", "Updates available ({}):").format(len(plan)) + RESET)
        for u in plan:
            say("  {}: {} -> {} ({})".format(u["unit"]["title"], u["old"], u["new"], u["src"]))
        ans = _ask(_t("Установить: a = все сразу, o = по одному, n = отмена [a]: ", "Install: a = all at once, o = one by one, n = cancel [a]: "))
        if ans is None or ans.lower() in ("n", "no", "н", "нет"):
            say(T[LANG]["cancelled"])
            return
        chosen = plan
        if ans.lower() in ("o", "о", "one"):
            chosen = []
            for k, u in enumerate(plan):
                a = _ask(_t("{}: {} -> {} ({}). y = да, n = пропустить, a = все оставшиеся, q = стоп [y]: ", "{}: {} -> {} ({}). y = yes, n = skip, a = all remaining, q = stop [y]: ").format(
                                       u["unit"]["title"], u["old"], u["new"], u["src"]))
                if a is None or a.lower() == "q":
                    break
                if a.lower() == "a":
                    chosen.extend(plan[k:])
                    break
                if is_yes(a):
                    chosen.append(u)
        if not chosen:
            say(_t("Нечего устанавливать.", "Nothing to install."))
            return
        known = set()
        for i in info.values():
            if i.get("mr"):
                known.add("mr:" + str(i["mr"]))
            if i.get("cf"):
                known.add("cf:" + str(i["cf"]))
        run_units([u["unit"] for u in chosen], s, folder, api_key, known)
    except KeyboardInterrupt:
        _CANCEL.clear()
        say()
        say(YELLOW + T[LANG]["interrupted"] + RESET)


NEW_MAX_PAGES = 4            #F67 #F74
CHAIN_DEPTH = 3          #F75
NEW_CACHE_TTL = 3600         #F76
PERIOD_UNITS = (("d", ("d", "day", "days", "д", "дн", "дня", "день", "дней")),
            ("w", ("w", "week", "weeks", "нед", "неделя", "недели", "неделю", "недель")),
            ("m", ("m", "mo", "mon", "month", "months", "мес", "месяц", "месяца", "месяцев")),
            ("y", ("y", "yr", "year", "years", "г", "год", "года", "лет")))


def today_dt():
    return datetime.date.today()

def date_back(today, n, unit):
    if unit == "d":
        return today - datetime.timedelta(days=n)
    if unit == "w":
        return today - datetime.timedelta(weeks=n)
    months = n if unit == "m" else 12 * n
    y, m = today.year, today.month - months
    while m <= 0:
        m += 12
        y -= 1
    return datetime.date(y, m, min(today.day, calendar.monthrange(y, m)[1]))


def parse_period(text):
    n, unit = 1, "w"
    for num, word in re.findall(r"(\d+)?\s*([a-zа-яё]+)", (text or "").lower()):
        hit = next((u for u, names in PERIOD_UNITS if word in names), None)
        if hit:
            n, unit = (int(num) if num else 1), hit
            break
    label = {'d': _t("{} дн.", "{}d"), 'w': _t("{} нед.", "{}w"), 'm': _t("{} мес.", "{}mo"), 'y': _t("{} г.", "{}y")}[unit]
    return date_back(today_dt(), n, unit), label.format(n)

def mr_new_projects(qn, since):
    key = f"nl_mr_v1:{qn.lower()}:{since}"
    cached = cache_get(key, ttl=NEW_CACHE_TTL)
    if cached != "MISS":
        return cached
    out, ok = [], True
    for p in range(NEW_MAX_PAGES):
        url = "https://api.modrinth.com/v2/search?query={}&index=newest&facets={}&limit={}&offset={}".format(
            urllib.parse.quote(qn), urllib.parse.quote(json.dumps([["project_type:mod"]])), PAGE_SIZE, p * PAGE_SIZE)
        data = http_get_json(url)
        if data is None:
            ok = False
            break
        hits = data.get('hits', [])
        for h in mr_only_mods(hits):
            d = (h.get('date_created') or "")[:10]
            if d >= since:
                slim = dict((k, h.get(k)) for k in ("project_id", "slug", "title", "description", "downloads", "categories"))
                slim['date'] = d
                out.append(slim)
        if len(hits) < PAGE_SIZE or (hits[-1].get('date_created') or "")[:10] < since:
            break
    if ok:
        cache_set(key, out)
    return out


def cf_new_projects(qn, api_key, since):
    key = f"nl_cf_v1:{qn.lower()}:{since}"
    cached = cache_get(key, ttl=NEW_CACHE_TTL)
    if cached != "MISS":
        return cached
    out, ok = [], True
    for p in range(NEW_MAX_PAGES):
        url = ("https://api.curseforge.com/v1/mods/search?gameId=432&classId={}&searchFilter={}&pageSize={}&index={}"
               "&sortField=11&sortOrder=desc").format(CF_CLASS_ID_MODS, urllib.parse.quote(qn), PAGE_SIZE, p * PAGE_SIZE)
        data = http_get_json(url, headers=cf_headers(api_key))
        if data is None:
            ok = False
            break
        items = cf_only_mods(data.get("data", []))
        dates = []
        for h in items:
            d = (h.get("dateReleased") or h.get("dateCreated") or "")[:10]
            dates.append(d)
            if d >= since:
                slim = slim_cf_hit(h)
                slim["date"] = d
                out.append(slim)
        if len(data.get("data", [])) < PAGE_SIZE or (dates and max(dates) < since):
            break
    if ok:
        cache_set(key, out)
    return out

def edges_of(side, pid, api_key):
    if side == "mr":
        return [(d[0], d[1]) for d in (modrinth_latest_version_deps(pid) or []) if len(d) >= 2 and d[1]]
    return [(d[0], d[1]) for d in (cf_latest_file_deps(pid, api_key) or []) if len(d) >= 2 and d[1]]


def title_of(side, pid, api_key):
    if side == "mr":
        return (mr_by_slug(pid) or {}).get('title') or str(pid)
    return (cf_mod_by_id(pid, api_key) or {}).get('name') or str(pid)


def dep_chain(side, edges, main_id, api_key, depth, seen):
    for kind, did in edges:
        if did == main_id and kind in ("required", "optional"):
            return []
    if depth > 1:
        for kind, did in edges:
            if kind != "required" or (side, did) in seen:
                continue
            seen.add((side, did))
            sub = dep_chain(side, edges_of(side, did, api_key), main_id, api_key, depth - 1, seen)
            if sub is not None:
                return [title_of(side, did, api_key)] + sub
    return None

def vers_of(pres):
    parts = []
    for lo in LOADERS:
        vs = sorted(pres.get(lo, ()), key=_vtup, reverse=True)
        if vs:
            parts.append(f"{LOADER_LABEL[lo]}: {', '.join(vs[:4])}{' ...' if len(vs) > 4 else ''}")
    return " | ".join(parts) or "-"


def collect_new(main_words, nt, since, mid, cid, api_key, qn):
    hits_mr = mr_new_projects(qn, since) if mid else []
    hits_cf = cf_new_projects(qn, api_key, since) if (cid and api_key) else []
    recs, lock = [], threading.Lock()

    def one(item):
        side, h = item
        if side == "mr":
            if h["project_id"] == mid:
                return
            rec = mr_record(normalize_modrinth_hit(h))
            main_id = mid
        else:
            if h["id"] == cid:
                return
            rec = cf_record(h, api_key)
            main_id = cid
        rec["date"] = h["date"]
        rec["chain"] = dep_chain(side, rec["edges"], main_id, api_key, CHAIN_DEPTH, set())
        text = _blob(rec["card"].get("title"), rec["card"].get("slug"))
        rec["lookalike"] = nt in text or all(w in text for w in main_words)
        with lock:
            recs.append(rec)

    _parallel_map(one, [("mr", h) for h in hits_mr] + [("cf", h) for h in hits_cf])
    return recs, len(hits_mr) + len(hits_cf)

def merge_new(recs):
    out = []
    for r in sorted(recs, key=lambda x: (x['side'], x['card'].get('title') or "")):
        slug = (r['card'].get('slug') or "").lower()
        for e in out:
            same = bool(slug) and any((x['card'].get('slug') or "").lower() == slug for x in e['sides'].values())
            if r['side'] not in e['sides'] and (same or norm_title(e['title']) == norm_title(r['card'].get('title'))):
                e['sides'][r['side']] = r
                break
        else:
            out.append({'title': r['card'].get('title') or "?", 'sides': {r['side']: r}})
    for e in out:
        rs = list(e['sides'].values())
        e['date'] = min(r['date'] for r in rs)
        e['pres'] = {}
        for r in rs:
            for lo, vs in r['pres'].items():
                e['pres'].setdefault(lo, set()).update(vs)
        chains = [r['chain'] for r in rs if r['chain'] is not None]
        e['chain'] = min(chains, key=len) if chains else None
        e['links'] = [r['card'].get('link') for r in rs if r['card'].get('link')]
        e['tag'] = "[M x CF]" if len(rs) == 2 else ("[M]" if "mr" in e['sides'] else "[CF]")
    return out


def created_since(e, since, api_key):
    if len(e["sides"]) == 2:
        return True
    try:
        if "mr" in e["sides"] and api_key:
            slim = other_on_cf(e["sides"]["mr"]["card"], api_key)
            raw = cf_mod_by_id(slim["id"], api_key) if slim else None
            d = ((raw or {}).get("dateReleased") or (raw or {}).get("dateCreated") or "")[:10]
        elif "cf" in e["sides"]:
            rec = e["sides"]["cf"]
            card = mr_for_cf(rec["card"], rec.get("hashes"))
            p = http_get_json("https://api.modrinth.com/v2/project/" + urllib.parse.quote(str(card["id"]), safe="")) if card else None
            d = ((p or {}).get("published") or "")[:10]
        else:
            return True
    except Exception:
        return True
    return not d or d >= since


def do_newaddons(args, api_key):
    n_old = 0
    tr = T[LANG]
    if not args:
        say(_t("Использование: newaddons <ссылка|slug> [период: 7d, 2w, 3m, неделя, 2 мес...] [загрузчик] [версия]",
                "Usage: newaddons <link|slug> [period: 7d, 2w, 3m, week, 2 months...] [loader] [version]"))
        return
    if not check_internet():
        say(f"{RED}{tr['no_internet']}{RESET}")
        return
    _CANCEL.clear()
    loaders, versions, rest = [], [], []
    for a in args[1:]:
        low = {"neo": "neoforge"}.get(a.lower(), a.lower())
        if low in LOADERS:
            loaders.append(low)
        elif REL_VER_RE.match(a):
            versions.append(a)
        else:
            rest.append(a)
    since_d, label = parse_period(" ".join(rest))
    since = since_d.isoformat()
    if not api_key:
        say(f"{YELLOW}{tr['search_cf_skipped']}{RESET}")
    mr_card, cf_slim = find_main_mod(args[0], api_key)
    if not mr_card and not cf_slim:
        say(f"{RED}{T[LANG]['mod_not_found']}{RESET}")
        return
    title = (mr_card or normalize_cf_hit(cf_slim))["title"]
    qn = _qname(title)
    words = [w for w in (_blob(x) for x in re.split(r"[\W_]+", qn)) if len(w) >= 3]
    say(f"{GREEN}{BOLD}" + _t("=== Новые аддоны к '{}' за {} (с {}) ===", "=== New addons of '{}' for {} (since {}) ===").format(
        title, label, since) + RESET)
    if cf_slim is None and api_key:
        say(f"{YELLOW}{_t('Этого мода нет на CurseForge (или не найден), смотрю только Modrinth.', 'Mod is not on CurseForge (or not found), looking at Modrinth only.')}" + RESET)
    try:
        recs, n = collect_new(words, _blob(qn), since, mr_card["id"] if mr_card else None,
                              cf_slim["id"] if cf_slim else None, api_key, qn)
    except KeyboardInterrupt:
        _CANCEL.clear()
        say(f"{YELLOW}{T[LANG]['interrupted']}{RESET}")
        return
    save_cache()
    items = [e for e in merge_new(recs) if created_since(e, since, api_key)]
    if loaders or versions:
        items = [e for e in items if any((not loaders or lo in loaders) and (not versions or v in versions)
                                         for lo, vs in e["pres"].items() for v in vs)]
    real = sorted([e for e in items if e["chain"] is not None], key=lambda e: (e["date"], e["title"].lower()), reverse=True)
    maybe = sorted([e for e in items if e["chain"] is None and any(r["lookalike"] for r in e["sides"].values())],
                   key=lambda e: (e["date"], e["title"].lower()), reverse=True)[:20]

    def show(e):
        if e["chain"] is None:
            how = _t("зависимость не указана", "no dependency declared")
        elif not e["chain"]:
            how = _t("напрямую", "directly")
        else:
            how = _t("через ", "via ") + " > ".join(e["chain"])
        say(f"{e['date']}  {e['title']} {e['tag']}  ({how})")
        say(f"    {vers_of(e['pres'])}")
        say(f"    {' | '.join(e['links'])}")

    if real:
        for e in real:
            show(e)
    else:
        say(_t("Новых аддонов за этот период не найдено.", "No new addons found for this period."))
    if maybe:
        say()
        say(BOLD + _t("Возможные (название похоже, зависимость не указана):",
                       "Possible (similar name, no dependency declared):") + RESET)
        for e in maybe:
            show(e)
    say(tr["commands"])


def main():
    choose_language()
    print_banner()
    api_key = load_cf_key()
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        except KeyboardInterrupt:
            say()
            break
        if not line:
            continue
        parts = line.split()
        if parts[0] in ("search", "bulk") and ('"' in line or "'" in line):
            try:
                parts = shlex.split(line)   #F29
            except ValueError:
                pass
        cmd = parts[0]
        args = parts[1:]

        try:
            if cmd == "key" and args:
                api_key=" ".join(args).strip()
                save_cf_key(api_key)
                say(f"{GREEN}{T[LANG]['key_set']}{RESET}")
            elif cmd == "search":
                do_search(args, api_key)
            elif cmd == "show":
                do_show(args, api_key)
            elif cmd == "save":
                do_save(args, api_key)
            elif cmd == "saveall":
                do_saveall(api_key)
            elif cmd == "bulk":
                do_bulk(args, api_key)
            elif cmd == "addons":
                do_addons(args, api_key)
            elif cmd == "build":
                do_build(args, api_key)
            elif cmd == "newaddons":
                do_newaddons(args, api_key)
            elif cmd == "importlink":
                do_importlink(args, api_key)
            elif cmd == "update":
                do_update(args, api_key)
            elif is_url(cmd):
                do_import_urls(line, api_key)
            elif cmd == "help":
                do_help()
            elif cmd == "exit":
                break
            else:
                say(T[LANG]["commands"])
        except KeyboardInterrupt:
            say()
            say(f"{YELLOW}{T[LANG]['bulk_interrupted']}{RESET}")
        except Exception as e:
            #F30
            say(f"{RED}{_t('Неожиданная ошибка', 'Unexpected error')}: {e}{RESET}") #F77

    save_cache() #Спасибо Диме за Английский перевод Thanks Dima for Eng localisation 


if __name__ == "__main__":
    main()
