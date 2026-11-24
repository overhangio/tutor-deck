SHORT_SLEEP_SECONDS = 0.1
PLUGINS_REQUIRE_LAUNCH_COOKIE_NAME = "plugins-require-launch"
COMMAND_EXECUTED_COOKIE_NAME = "command-executed"
ITEMS_PER_PAGE = 100

# Core Open edX services whose logs can be viewed. Plugins may define more: the
# service input also accepts free-form service names.
OPENEDX_SERVICES = [
    "caddy",
    "cms",
    "cms-worker",
    "lms",
    "lms-worker",
    "meilisearch",
    "mongodb",
    "mysql",
    "redis",
    "smtp",
]
