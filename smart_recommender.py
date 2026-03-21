# smart_recommender.py
import datetime

class Model:
    """模型信息类"""
    def __init__(self, name, family, params, multimodal, cpu_req, gpu_req, ram_req_gb, release_date):
        self.name = name
        self.family = family
        self.params = params  # 参数量，例如 0.8B, 3B
        self.multimodal = multimodal  # 是否支持多模态
        self.cpu_req = cpu_req
        self.gpu_req = gpu_req
        self.ram_req_gb = ram_req_gb
        self.release_date = release_date  # datetime 对象

class UserHardware:
    """用户硬件信息类"""
    def __init__(self, cpu_cores, gpu_name, ram_gb):
        self.cpu_cores = cpu_cores
        self.gpu_name = gpu_name
        self.ram_gb = ram_gb

class UserPreference:
    """用户偏好"""
    def __init__(self, speed_priority=False, capability_priority=False, need_multimodal=False):
        self.speed_priority = speed_priority
        self.capability_priority = capability_priority
        self.need_multimodal = need_multimodal

class SmartRecommender:
    """智能推荐系统"""
    def __init__(self, models):
        self.models = models

    def score_model(self, model, hardware: UserHardware, preference: UserPreference):
        score = 0

        # 硬件适配评分
        if hardware.cpu_cores >= model.cpu_req:
            score += 2
        if model.gpu_req:
            if hardware.gpu_name:
                score += 3
            else:
                score -= 5  # 无GPU但需要GPU
        if hardware.ram_gb >= model.ram_req_gb:
            score += 2
        else:
            score -= 2

        # 多模态需求
        if preference.need_multimodal and model.multimodal:
            score += 3
        elif preference.need_multimodal and not model.multimodal:
            score -= 3

        # 用户偏好加权
        if preference.speed_priority:
            # 参数量小的模型得分高
            if 'B' in model.params:
                size = float(model.params.replace('B', ''))
                score += max(0, 5 - size)  # 轻量模型更优
        if preference.capability_priority:
            # 参数量大的模型得分高
            if 'B' in model.params:
                size = float(model.params.replace('B', ''))
                score += size  # 大模型更优

        # 时间新旧加分，越新模型得分越高
        days_since_release = (datetime.datetime.now() - model.release_date).days
        score += max(0, 30 - days_since_release // 30)  # 最近30天的模型加分

        return score

    def recommend_top_n(self, hardware: UserHardware, preference: UserPreference, top_n=3):
        """返回 top-N 模型"""
        scored_models = []
        for model in self.models:
            score = self.score_model(model, hardware, preference)
            scored_models.append((score, model))
        scored_models.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored_models[:top_n]]


# -------------------------
# 示例用法
# -------------------------
if __name__ == "__main__":
    import datetime

    # 模型库
    models = [
        Model("Qwen3.5 0.8B", "qwen3.5", "0.8B", False, 8, None, 16, datetime.datetime(2026, 3, 15)),
        Model("Qwen2.5 3B", "qwen2.5", "3B", False, 8, None, 16, datetime.datetime(2025, 6, 6)),
        Model("Qwen3.5 13B", "qwen3.5", "13B", True, 12, "RTX 4090", 32, datetime.datetime(2026, 2, 10)),
    ]

    # 用户硬件
    hw = UserHardware(cpu_cores=18, gpu_name=None, ram_gb=32)

    # 用户偏好
    pref = UserPreference(speed_priority=True, capability_priority=False, need_multimodal=False)

    recommender = SmartRecommender(models)
    top_models = recommender.recommend_top_n(hw, pref, top_n=3)

    print("Top recommended models:")
    for m in top_models:
        print(f"- {m.name} ({m.params})")