from model_catalog import DEPLOY_CATALOG

print("支持的一键部署模型家族：")
for family in DEPLOY_CATALOG:
    print("-", family["family"])

print("\n第一个家族的第一个部署标签：")
print(DEPLOY_CATALOG[0]["deploy_options"][0]["id"])