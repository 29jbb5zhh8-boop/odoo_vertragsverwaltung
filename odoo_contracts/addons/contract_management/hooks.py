def post_init_hook(env):
    env["res.lang"].search([("code", "=", "de_DE")]).write({"date_format": "%d.%m.%Y"})
    env["res.lang"].search([("code", "=", "en_US")]).write({"date_format": "%m/%d/%Y"})
