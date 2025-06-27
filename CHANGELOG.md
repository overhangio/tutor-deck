# Changelog

This file includes a history of past releases. Changes that were not yet added to a release are in the [changelog.d/](./changelog.d) folder.

<!--
⚠️ DO NOT ADD YOUR CHANGES TO THIS FILE! (unless you want to modify existing changelog entries in this file)
Changelog entries are managed by scriv. After you have made some changes to Tutor, create a changelog entry with:

    make changelog-entry

Edit and commit the newly-created file in changelog.d.

If you need to create a new release, create a separate commit just for that. It is important to respect these
instructions, because git commits are used to generate release notes:
  - Collect changelog entries with `make changelog`
  - The title of the commit should be the same as the CHANGELOG.md file section title: "vX.Y.Z (year-month-day)".
  - The commit message should be copy-pasted from the release section.
  - Have a look at other release commits for reference.
-->

<!-- scriv-insert-here -->

<a id='changelog-20.0.0'></a>
## v20.0.0 (2025-06-02)

 - [Bugfix] Add logs script to all pages so each page can handle completion of a command itself and not delegate it to a page with logs script. (by @mlabeeb03)

-   [Improvement] Remove the `last-log-file` cookie and use `is_thread_alive` function to check the status of running commands. (by @mlabeeb03)

- [Feature] Only allow command cancellation from relevant page. (by @mlabeeb03)
- [Feature] Add link to developer panel while command is in progress. (by @mlabeeb03)

- 💥[Feature] Upgrade to Teak. (by @mlabeeb03)

<a id='changelog-19.0.2'></a>
## v19.0.2 (2025-04-16)

- [Bugfix] Prevent images in plugin description from overflowing. (by @mlabeeb03)

<a id='changelog-19.0.1'></a>
## v19.0.1 (2025-04-16)

- [Bugfix] Include CSS files in built pypi assets. (by @regisb)

<a id='changelog-19.0.0'></a>
## v19.0.0 (2025-04-10)

- [Feature] Initial release 🌅 (by @mlabeeb03).
