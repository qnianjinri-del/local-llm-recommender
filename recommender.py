from datetime import datetime, timezone
import re

from model_catalog import DEPLOY_CATALOG


def get_max_vram_gb(hardware_info):
    gpus = hardware_info.get("gpus", [])
    if not gpus:
        return 0
    return max(gpu.get("vram_gb", 0) for gpu in gpus)


def get_cpu_cores(hardware_info):
    return hardware_info.get("cpu_cores_logical", 0)


def get_hardware_mode(hardware_info):
    return "gpu" if get_max_vram_gb(hardware_info) > 0 else "cpu_only"


def parse_param_to_billions(param_label):
    text = str(param_label).strip().lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([bm])", text)
    if not match:
        return 0.0
    value = float(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return value / 1000.0
    return value


def build_candidate_pool(category="general"):
    candidates = []

    for family in DEPLOY_CATALOG:
        family_name = family["family"]
        family_display_name = family.get("family_display_name", family_name)

        for option in family.get("deploy_options", []):
            if option.get("category") != category:
                continue

            candidates.append({
                "family": family_name,
                "family_display_name": family_display_name,
                "deploy_id": option["id"],
                "display_name": option["display_name"],
                "param_label": option.get("param_label", "-"),
                "param_billions": parse_param_to_billions(option.get("param_label", "0b")),
                "category": option["category"],
                "min_ram_gb": option.get("min_ram_gb", 0),
                "recommended_vram_gb": option.get("recommended_vram_gb", 0),
                "download_size_gb": option.get("download_size_gb", 0),
                "notes": option.get("notes", ""),
            })

    return candidates


def classify_tier(candidate, hardware_info):
    ram_gb = hardware_info.get("ram_gb", 0)
    max_vram_gb = get_max_vram_gb(hardware_info)
    mode = get_hardware_mode(hardware_info)

    min_ram = candidate["min_ram_gb"]
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    param_b = candidate.get("param_billions", 0)
    ram_margin = ram_gb - min_ram
    vram_margin = max_vram_gb - suggested_vram

    if mode == "cpu_only":
        if ram_margin < -4:
            return "avoid"
        if ram_margin < 0:
            return "tryable"

        if suggested_vram == 0:
            return "suitable"

        if ram_margin >= 12 and param_b <= 14:
            return "suitable"
        if ram_margin >= 6 and param_b <= 14:
            return "tryable"
        return "avoid"

    # GPU mode
    if ram_margin < -4:
        return "avoid"
    if ram_margin < 0:
        return "tryable"

    if suggested_vram == 0:
        return "suitable"

    if vram_margin >= 0:
        return "suitable"
    if max_vram_gb >= max(4, suggested_vram - 4):
        return "tryable"
    if ram_margin >= 10 and param_b <= 8:
        return "tryable"
    return "avoid"


def is_model_runnable(candidate, hardware_info):
    return classify_tier(candidate, hardware_info) == "suitable"


def build_reason_text(candidate):
    return (
        f"当前推荐参数 {candidate['param_label']}；"
        f"最低内存 {candidate['min_ram_gb']}GB；"
        f"建议显存 {candidate['recommended_vram_gb']}GB；"
        f"下载体积 {candidate['download_size_gb']}GB"
    )


def parse_last_modified_datetime(last_modified):
    if not last_modified:
        return None

    text = str(last_modified).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def build_freshness_badge(last_modified):
    dt = parse_last_modified_datetime(last_modified)
    if not dt:
        return ""

    now = datetime.now(timezone.utc)
    delta_days = max(0, (now - dt).days)

    if delta_days <= 30:
        return "新发布"
    if delta_days <= 90:
        return "最近更新"
    return ""


def freshness_rank(last_modified):
    dt = parse_last_modified_datetime(last_modified)
    if not dt:
        return 0
    now = datetime.now(timezone.utc)
    delta_days = max(0, (now - dt).days)
    if delta_days <= 30:
        return 3
    if delta_days <= 90:
        return 2
    return 1


def score_candidate(candidate, hardware_info, user_preference="balanced", source_model=None):
    ram_gb = hardware_info.get("ram_gb", 0)
    max_vram_gb = get_max_vram_gb(hardware_info)
    cpu_cores = get_cpu_cores(hardware_info)
    mode = get_hardware_mode(hardware_info)

    min_ram = candidate["min_ram_gb"]
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    size = candidate["download_size_gb"]
    param_b = candidate.get("param_billions", 0)

    score = 42
    ram_margin = max(0, ram_gb - min_ram)
    score += min(ram_margin, 32) * 0.4

    if mode == "gpu":
        if suggested_vram == 0:
            score += 3
        else:
            vram_margin = max_vram_gb - suggested_vram
            score += max(-6, min(vram_margin, 12)) * 0.8
    else:
        if suggested_vram > 0:
            score -= 5
        if min_ram <= 16:
            score += 4

    if cpu_cores >= 16:
        score += 6
    elif cpu_cores >= 8:
        score += 3

    if user_preference == "speed":
        score += max(0, 18 - size * 3.0)
        score += max(0, 10 - min_ram * 0.35)
        score -= param_b * 0.35
    elif user_preference == "capability":
        score += min(param_b, 70) * 1.7
        score += size * 0.35
        if ram_margin < 4:
            score -= 6
    else:
        score += min(param_b, 20) * 2.0
        score += max(0, 8 - max(0, size - 8))
        if ram_margin < 2:
            score -= 12
        elif ram_margin < 4:
            score -= 6

    if source_model:
        last_modified = str(source_model.get("last_modified", ""))
        if last_modified:
            score += 4

    return round(score, 2)


def build_summary_tag(candidate, hardware_info, user_preference="balanced"):
    param_b = candidate.get("param_billions", 0)
    min_ram = candidate["min_ram_gb"]
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    has_gpu = get_max_vram_gb(hardware_info) > 0

    if user_preference == "speed":
        if param_b <= 1.0:
            return "极速上手"
        if param_b <= 4.0:
            return "轻量首选"
        return "更快落地"

    if user_preference == "capability":
        if param_b >= 14:
            return "高能档位"
        if param_b >= 7:
            return "更强能力"
        return "能力优先"

    if param_b <= 1.0:
        return "入门推荐"
    if param_b <= 4.0:
        return "均衡首选"
    if not has_gpu and suggested_vram > 0:
        return "可尝试"
    if min_ram <= 24:
        return "日常常用"
    return "进阶选择"


def build_deploy_level(candidate, hardware_info):
    mode = get_hardware_mode(hardware_info)
    ram_gb = hardware_info.get("ram_gb", 0)
    min_ram = candidate["min_ram_gb"]
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    max_vram = get_max_vram_gb(hardware_info)

    if min_ram <= 10:
        return "低门槛"
    if mode == "cpu_only":
        if min_ram <= 20 and suggested_vram == 0:
            return "中门槛"
        if ram_gb - min_ram <= 2:
            return "接近上限"
        return "高门槛"

    if min_ram <= 20 and (suggested_vram == 0 or max_vram >= suggested_vram):
        return "中门槛"
    if ram_gb - min_ram <= 2:
        return "接近上限"
    return "高门槛"


def build_runtime_assessment(candidate, hardware_info):
    mode = get_hardware_mode(hardware_info)
    ram_gb = hardware_info.get("ram_gb", 0)
    max_vram_gb = get_max_vram_gb(hardware_info)

    min_ram = candidate["min_ram_gb"]
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    ram_margin = ram_gb - min_ram
    vram_margin = max_vram_gb - suggested_vram

    if mode == "cpu_only":
        if suggested_vram > 0:
            if ram_margin >= 12:
                return "偏重", "这档模型能在纯 CPU 环境尝试，但会更吃内存，适合愿意多等一点的情况。"
            if ram_margin >= 6:
                return "较吃资源", "这档模型理论上可试，但在无独显电脑上响应会更慢。"
            return "较吃资源", "这档模型更依赖显卡或更充足的内存，纯 CPU 体验通常不会太理想。"

        if ram_margin >= 12:
            return "轻快", "这档模型对你的内存压力比较小，启动和日常问答都会更轻松。"
        if ram_margin >= 6:
            return "均衡", "这档模型在你的纯 CPU 机器上属于比较稳妥的常用选择。"
        if ram_margin >= 2:
            return "偏重", "这档模型可以跑，但连续长对话或复杂任务时会更吃资源。"
        return "较吃资源", "这档模型已经接近你当前内存上限，体验会偏重。"

    # GPU mode
    if suggested_vram > 0:
        if ram_margin >= 8 and vram_margin >= 4:
            return "轻快", "内存和显存都有余量，这档模型在你的机器上会比较从容。"
        if ram_margin >= 4 and vram_margin >= 0:
            return "均衡", "这档模型在你的显卡和内存范围内，适合作为日常主力。"
        if ram_margin >= 2 and vram_margin >= -2:
            return "偏重", "这档模型可以跑，但已经比较接近当前显存或内存边界。"
        return "较吃资源", "这档模型已经比较贴近你的硬件上限，更适合把它当作尝鲜或进阶尝试。"

    if ram_margin >= 10:
        return "轻快", "这档模型对显卡依赖不高，而且内存余量充足，整体会比较顺手。"
    if ram_margin >= 4:
        return "均衡", "这档模型的体积和负载比较适中，适合作为常用模型。"
    if ram_margin >= 1:
        return "偏重", "这档模型能跑，但长时间使用时会明显更吃资源。"
    return "较吃资源", "这档模型已经接近当前机器内存边界。"


def format_param_list(labels):
    return " / ".join(labels) if labels else "无"


def build_family_param_profile(family_candidates, hardware_info):
    all_params = []
    suitable = []
    tryable = []
    avoid = []

    for candidate in sorted(family_candidates, key=lambda x: x.get("param_billions", 0)):
        label = candidate["param_label"]
        all_params.append(label)
        tier_class = classify_tier(candidate, hardware_info)
        if tier_class == "suitable":
            suitable.append(label)
        elif tier_class == "tryable":
            tryable.append(label)
        else:
            avoid.append(label)

    return {
        "all_params": all_params,
        "suitable_params": suitable,
        "tryable_params": tryable,
        "avoid_params": avoid,
        "all_params_text": format_param_list(all_params),
        "suitable_params_text": format_param_list(suitable),
        "tryable_params_text": format_param_list(tryable),
        "avoid_params_text": format_param_list(avoid),
    }


def build_user_friendly_note(candidate, hardware_info, user_preference, family_profile):
    family_name = candidate["family_display_name"]
    suitable_text = family_profile["suitable_params_text"]
    tryable_text = family_profile["tryable_params_text"]
    hardware_mode = get_hardware_mode(hardware_info)

    parts = []
    if user_preference == "speed":
        parts.append(f"{family_name} 这一家族里，我优先挑了更容易下载和启动的档位。")
    elif user_preference == "capability":
        parts.append(f"{family_name} 这一家族里，我优先挑了更偏效果和能力的档位。")
    else:
        parts.append(f"{family_name} 这一家族里，我优先挑了对大多数用户更稳妥的档位。")

    if hardware_mode == "cpu_only":
        parts.append("你的机器当前按纯 CPU 方案判断，所以我会更保守地处理大参数。")
    else:
        parts.append("你的机器有可用显卡，所以同等内存下可以更积极地考虑更高参数。")

    if suitable_text != "无":
        parts.append(f"按你这台电脑的情况，更适合的参数档位有：{suitable_text}。")
    if tryable_text != "无":
        parts.append(f"如果你愿意多等一点，也可以尝试：{tryable_text}。")

    parts.append(f"当前推荐的 {candidate['param_label']} 档更适合作为现在就能部署的选择。")

    base_note = candidate.get("notes", "").strip()
    if base_note:
        parts.append(f"补充说明：{base_note}")

    return " ".join(parts)


def build_tier_advice_text(candidate, family_profile):
    return (
        f"全部参数：{family_profile['all_params_text']}\n"
        f"适合你的电脑：{family_profile['suitable_params_text']}\n"
        f"可尝试：{family_profile['tryable_params_text']}\n"
        f"暂不建议：{family_profile['avoid_params_text']}"
    )


def build_deploy_tip(candidate, family_profile, user_preference="balanced"):
    suitable = family_profile["suitable_params_text"]
    size = candidate["download_size_gb"]
    param_label = candidate["param_label"]

    if user_preference == "speed":
        return f"当前推荐 {param_label} 档，预计下载约 {size}GB，适合先把本地部署跑通。"
    if user_preference == "capability":
        return f"当前推荐 {param_label} 档，属于这个家族里你现在能较稳妥尝试的更强档位。"
    return f"当前推荐 {param_label} 档；如果你后面想升级，同一家族更适合你的参数范围大致是：{suitable}。"


def compute_resource_gap(candidate, hardware_info):
    ram_gb = hardware_info.get("ram_gb", 0)
    max_vram_gb = get_max_vram_gb(hardware_info)

    ram_short = max(0.0, round(candidate["min_ram_gb"] - ram_gb, 1))
    suggested_vram = candidate.get("recommended_vram_gb", 0)
    vram_short = max(0.0, round(suggested_vram - max_vram_gb, 1)) if suggested_vram > 0 else 0.0

    return {
        "ram_short": ram_short,
        "vram_short": vram_short,
    }


def build_gap_text(candidate, hardware_info):
    gap = compute_resource_gap(candidate, hardware_info)
    parts = []

    if gap["ram_short"] > 0:
        parts.append(f"内存还差约 {gap['ram_short']}GB")
    if gap["vram_short"] > 0:
        parts.append(f"建议显存还差约 {gap['vram_short']}GB")

    if not parts:
        if candidate.get("recommended_vram_gb", 0) > 0 and get_max_vram_gb(hardware_info) == 0:
            return "主要受显卡条件影响"
        return "主要是为了留出更稳妥的运行余量"

    return "，".join(parts)


def build_family_upgrade_explanation(best_candidate, family_candidates, hardware_info):
    current_b = best_candidate.get("param_billions", 0)

    larger_candidates = sorted(
        [c for c in family_candidates if c.get("param_billions", 0) > current_b],
        key=lambda x: x.get("param_billions", 0),
    )

    if not larger_candidates:
        return "这个家族里已经没有比当前推荐更大的本地参数档位了。"

    suitable = [c for c in larger_candidates if classify_tier(c, hardware_info) == "suitable"]
    tryable = [c for c in larger_candidates if classify_tier(c, hardware_info) == "tryable"]
    avoid = [c for c in larger_candidates if classify_tier(c, hardware_info) == "avoid"]

    if suitable:
        first_suitable = suitable[0]
        return (
            f"同家族更大的 {first_suitable['param_label']} 其实也能跑，"
            f"但当前排序更优先考虑了速度、资源余量和整体均衡性，所以暂时没有把它排在前面。"
        )

    if tryable:
        first_tryable = tryable[0]
        text = (
            f"同家族更大的 {first_tryable['param_label']} 还可以尝试，"
            f"但会更吃资源，所以当前没有把它排在前面。"
        )
        if avoid:
            first_avoid = avoid[0]
            text += f"再往上的 {first_avoid['param_label']} 则{build_gap_text(first_avoid, hardware_info)}。"
        return text

    if avoid:
        first_avoid = avoid[0]
        return (
            f"同家族更大的 {first_avoid['param_label']} 没被推荐，"
            f"主要因为 {build_gap_text(first_avoid, hardware_info)}。"
        )

    return "当前推荐已经是这个家族里更合适的本地参数档位。"


def build_limit_examples(family_to_candidates, hardware_info, limit=5):
    examples = []

    for family_candidates in family_to_candidates.values():
        sorted_family = sorted(family_candidates, key=lambda x: x.get("param_billions", 0))
        suitable = [c for c in sorted_family if classify_tier(c, hardware_info) == "suitable"]
        if not suitable:
            avoid_or_try = [c for c in sorted_family if classify_tier(c, hardware_info) != "suitable"]
            if avoid_or_try:
                first = avoid_or_try[0]
                examples.append(
                    f"{first['family_display_name']} 的 {first['param_label']} 当前还不合适，{build_gap_text(first, hardware_info)}。"
                )
            continue

        largest_suitable = suitable[-1]
        larger = [c for c in sorted_family if c.get('param_billions', 0) > largest_suitable.get('param_billions', 0)]
        if larger:
            next_one = larger[0]
            examples.append(
                f"{largest_suitable['family_display_name']} 更大的 {next_one['param_label']} 没进推荐前列，主要因为 {build_gap_text(next_one, hardware_info)}。"
            )

    if not examples:
        return []

    examples.sort(key=len)
    return examples[:limit]


def build_hardware_limit_summary(candidates, family_to_candidates, hardware_info):
    suitable_candidates = [c for c in candidates if classify_tier(c, hardware_info) == "suitable"]
    tryable_candidates = [c for c in candidates if classify_tier(c, hardware_info) == "tryable"]
    hardware_mode = get_hardware_mode(hardware_info)

    if suitable_candidates:
        sorted_suitable = sorted(suitable_candidates, key=lambda x: x.get("param_billions", 0))
        min_label = sorted_suitable[0]["param_label"]
        max_label = sorted_suitable[-1]["param_label"]
        summary = f"按当前硬件，整体更适合 {min_label} 到 {max_label} 这一档的本地模型。"
    else:
        summary = "按当前硬件，当前内置目录里没有特别稳妥的本地参数档位。"

    if hardware_mode == "cpu_only":
        summary += " 当前按纯 CPU 规则判断，所以对更大的参数会更保守。"
    else:
        summary += " 当前按有独显规则判断，所以会更积极地利用显存余量。"

    if tryable_candidates:
        tryable_labels = []
        for c in sorted(tryable_candidates, key=lambda x: x.get("param_billions", 0)):
            label = f"{c['family_display_name']} {c['param_label']}"
            if label not in tryable_labels:
                tryable_labels.append(label)
            if len(tryable_labels) >= 3:
                break
        summary += f" 再往上一些的 {' / '.join(tryable_labels)} 可以尝试，但会更吃资源。"
    else:
        summary += " 再往上的大参数档位大多会受内存或显存门槛限制。"

    examples = build_limit_examples(family_to_candidates, hardware_info, limit=5)
    examples_text = "\n".join([f"• {line}" for line in examples]) if examples else "• 当前没有额外的大参数解释。"

    return {
        "summary": summary,
        "examples": examples,
        "examples_text": examples_text,
    }


def choose_sort_key(item, sort_mode):
    if sort_mode == "lightweight":
        return (item["download_size_gb"], item["min_ram_gb"], -item["score"])
    if sort_mode == "capability":
        return (-item["param_billions"], -item["score"], item["download_size_gb"])
    if sort_mode == "freshness":
        return (-freshness_rank(item.get("last_modified")), -item["score"], item["download_size_gb"])
    return (-item["score"], item["download_size_gb"])


def recommend_from_recent_models(
    recent_models,
    hardware_info,
    category="general",
    user_preference="balanced",
    sort_mode="overall",
    top_n=8,
):
    candidates = build_candidate_pool(category=category)

    family_to_recent_model = {}
    for model in recent_models:
        family = model.get("family")
        if family and family not in family_to_recent_model:
            family_to_recent_model[family] = model

    family_to_candidates = {}
    for candidate in candidates:
        family_to_candidates.setdefault(candidate["family"], []).append(candidate)

    limit_report = build_hardware_limit_summary(candidates, family_to_candidates, hardware_info)
    scored_results = []

    for family, family_candidates in family_to_candidates.items():
        family_profile = build_family_param_profile(family_candidates, hardware_info)
        runnable_candidates = [c for c in family_candidates if classify_tier(c, hardware_info) == "suitable"]

        if not runnable_candidates:
            continue

        source_model = family_to_recent_model.get(family, {
            "id": family_candidates[0]["deploy_id"],
            "last_modified": None,
            "family": family,
            "source": "offline_catalog",
        })

        best_candidate = None
        best_score = None
        for candidate in runnable_candidates:
            score = score_candidate(candidate, hardware_info, user_preference, source_model)
            if best_candidate is None or score > best_score:
                best_candidate = candidate
                best_score = score

        runtime_feel, runtime_note = build_runtime_assessment(best_candidate, hardware_info)

        result = {
            "family": family,
            "family_display_name": best_candidate["family_display_name"],
            "source_model_id": source_model.get("id"),
            "last_modified": source_model.get("last_modified"),
            "deploy_id": best_candidate["deploy_id"],
            "display_name": best_candidate["display_name"],
            "current_param": best_candidate["param_label"],
            "param_billions": best_candidate["param_billions"],
            "min_ram_gb": best_candidate["min_ram_gb"],
            "recommended_vram_gb": best_candidate["recommended_vram_gb"],
            "all_params_text": family_profile["all_params_text"],
            "suitable_params_text": family_profile["suitable_params_text"],
            "tryable_params_text": family_profile["tryable_params_text"],
            "avoid_params_text": family_profile["avoid_params_text"],
            "tier_advice_text": build_tier_advice_text(best_candidate, family_profile),
            "notes": build_user_friendly_note(best_candidate, hardware_info, user_preference, family_profile),
            "download_size_gb": best_candidate["download_size_gb"],
            "score": best_score,
            "reason": build_reason_text(best_candidate),
            "summary_tag": build_summary_tag(best_candidate, hardware_info, user_preference),
            "freshness_badge": build_freshness_badge(source_model.get("last_modified")),
            "deploy_level": build_deploy_level(best_candidate, hardware_info),
            "deploy_tip": build_deploy_tip(best_candidate, family_profile, user_preference),
            "not_recommended_explanation": build_family_upgrade_explanation(best_candidate, family_candidates, hardware_info),
            "limit_summary": limit_report["summary"],
            "limit_examples_text": limit_report["examples_text"],
            "runtime_feel": runtime_feel,
            "runtime_note": runtime_note,
            "hardware_mode": get_hardware_mode(hardware_info),
            "sort_mode_used": sort_mode,
        }
        scored_results.append(result)

    scored_results.sort(key=lambda item: choose_sort_key(item, sort_mode))

    for index, item in enumerate(scored_results):
        item["top_badge"] = "当前首选" if index == 0 else ""

    return scored_results[:top_n]
