# Auto-Finder (Mod Finder / Auto-Modpacker)

*English · [Русский](README.ru.md)*

A command-line tool for Minecraft players, modpack makers, and server admins. It searches **Modrinth and CurseForge at the same time**, merges the same mod from both sites into one entry, finds addons for a mod, and builds ready modpacks. Pure Python, no dependencies, works on Windows, Linux, macOS, and Termux.

## Why it exists, and what makes it different

Sometimes, manually searching for "all add-ons for X" can take hours. Auto-Finder solves this: it gathers potential candidates through a search process and checks each one’s dependency list for the required mod—including "add-ons for add-ons." It treats both platforms as a single unified catalog, selects the most recent file compatible with your specific version of Minecraft and mod loader, and presents the results in two formats: a detailed report and a compact version optimized for AI models—helping to save tokens while ensuring the most relevant mods are selected.

## Most useful features

- **`bulk`**: takes the page or a category (a tag or a category link from either site), finds addons for every mod, and saves everything to `found_mods/mods.txt` and `found_mods/mods_ai.txt`. The list grows between runs.
- **`build`**: modpack builder. Give it a main mod, get its addons sorted into loader + Minecraft version blocks, with exclusive and missing marks, ready `.jar` files in `found_mods/modpacks/`, and `.mrpack` export. The same mod on both sites is matched by file hash.
- **`importlink`**: paste Modrinth/CurseForge links (or just drop them into the script), and it downloads the newest file for your version and loader, with required dependencies.
- **`update`**: updates the mods in a folder. It identifies mods by SHA1 / CurseForge fingerprint, finds newer files on both sites, and moves old files to `_old`.

## How to use

1. Install Python 3. Download `Auto-Finder-Public-Release.py` and run it: `python Auto-Finder-Public-Release.py`.
2. Choose a language (`ru` / `en`).
3. For CurseForge, get a free API key at console.curseforge.com and save it with `key <your key>`. Without a key only Modrinth is used.
4. Type commands at the `>` prompt. Example: `search optimization` shows a numbered list, `show 3` opens a full card, `save 3` adds it to your list.

A *slug* is the end of a mod's link, for example `sodium` in `https://modrinth.com/mod/sodium`.

## Other features

- `search <tag | name:title | link>`: search by tags (AND), by title (`name:iron_man`), or by a category link.
- `show <N>`, `save <N>`, `saveall`: inspect and save results of the last search.
- `addons <slug | modid>`: possible addons of one mod (the list is not complete, see the note in the command).
- `newaddons <link | slug> [period] [loader] [version]`: new addons created in the last week, month, and so on.
- Download filters such as `mr=5k cf=1m` (skip mods with too few downloads), `prefer CF|M`, and `only releases`.
- `help` shows all commands, `exit` quits.

## Rules of use

The code is public to read, learn from, and use, but this is **not open source**. By using, copying, or modifying it you accept [LICENSE.md](LICENSE.md). In short:

- **Non-commercial use only.** No selling, paid access, microtransactions, paid ranks, ads, or training paid AI products. Personal, study, and non-profit use is fine, and so are videos and reviews.
- **Credit is required** in your README, in your product, and in its documentation: *Based on Auto-Finder by A Simple Block (https://github.com/SimpleBlockDev/Auto-Finder)*.
- **Excluded parties** listed in [EXCLUDED.md](EXCLUDED.md) get no license. Parties in [LICENSED.md](LICENSED.md) have permission in advance.
- **Donation links are allowed** if voluntary and with no perks. Demanding a donation ends your license.
- Modified copies must stay under this license and be marked as changed.
- Commercial licenses: https://discord.gg/ntnpZ5EE, asimpleblockdev@gmail.com.

Read the full text in LICENSE.md. It prevails over this summary.

## Enjoy!

Found a bug or have an idea? Open an issue. Happy modding!
