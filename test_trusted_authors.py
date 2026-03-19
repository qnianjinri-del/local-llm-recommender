from model_catalog import DEPLOY_CATALOG

for family in DEPLOY_CATALOG:
    print(family["family"], "=>", family["trusted_authors"])