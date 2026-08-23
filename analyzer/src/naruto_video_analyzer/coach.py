"""Offline tactical coaching for one Naruto Mobile character.

The coach turns reviewed visual candidates into human-readable suggestions. It
does not click, inject input, attach to an emulator, or control a game client.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Recommendation:
    timestamp_s: float
    priority: str
    situation: str
    advice: str
    rationale: str
    confidence: float
    evidence: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        return asdict(self)


URASHIKI_PROFILE: dict[str, Any] = {
    "id": "urashiki_astro_fisher",
    "name": "大筒木浦式·异星钓者",
    "version": "0.1-reference",
    "source_policy": "参考资料整理；必须由录像审核者确认实际版本与帧数据",
    "principles": [
        "一技能命中后再把普攻资源转成属性攻击，不在中立阶段盲目消耗。",
        "钓取查克拉后，普攻后摇下拉摇杆进入对应属性终结分支。",
        "技能未命中或敌方替身可用时，优先拉开距离并观察红圈/受击状态。",
        "受击和血条变化只是视觉候选，必须人工确认是否真的命中。",
    ],
    "action_vocabulary": [
        "保持中距离",
        "一技能·钓星之钩",
        "普攻 1A-4A",
        "普攻后摇下拉摇杆",
        "观察替身与受击",
        "拉开距离",
        "奥义收尾",
    ],
}


KAKASHI_PROFILE: dict[str, Any] = {
    "id": "kakashi_susanoo",
    "name": "旗木卡卡西·须佐能乎",
    "version": "0.1-reference",
    "source_policy": "参考资料整理；必须由录像审核者确认实际版本与帧数据",
    "principles": [
        "普通普攻与上下特殊普攻可以在 1A-4A 间衔接，特殊普攻 4A 雷传后不要继续贪后续。",
        "上拉 3A 的高跳可用于规避部分地面攻击，下拉 2A 的蓄力雷切可边蓄力边调整位置。",
        "二技能一段是虚化/无敌窗口，二段是雷切手里剑；先确认敌方动作再决定是否转入组合技。",
        "神威抓取或奥义收尾需要结合命中、血条和敌方替身状态确认，未命中时优先撤出。",
    ],
    "action_vocabulary": [
        "保持中距离",
        "普攻 1A-4A",
        "上拉特殊普攻",
        "下拉特殊普攻",
        "神威·左",
        "神威·右一段虚化",
        "神威·右二段手里剑",
        "须佐能乎组合技",
        "奥义·神威雷切",
    ],
}


PROFILES = {
    URASHIKI_PROFILE["id"]: URASHIKI_PROFILE,
    KAKASHI_PROFILE["id"]: KAKASHI_PROFILE,
}


def _event_fields(event: dict[str, Any]) -> tuple[str, float, str]:
    return (
        str(event.get("event", "unknown")),
        float(event.get("timestamp_s", 0.0)),
        str(event.get("source", "unknown")),
    )


def _recommend(
    timestamp_s: float,
    priority: str,
    situation: str,
    advice: str,
    rationale: str,
    confidence: float,
    *evidence: str,
) -> Recommendation:
    return Recommendation(
        timestamp_s=round(timestamp_s, 3),
        priority=priority,
        situation=situation,
        advice=advice,
        rationale=rationale,
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        evidence=tuple(evidence),
    )


def coach_events(events: Iterable[dict[str, Any]], *, character: str = "urashiki_astro_fisher") -> list[Recommendation]:
    """Generate review suggestions from a candidate timeline.

    The input is intentionally a JSON-friendly event list. Candidate signals
    are treated as uncertain observations; a recommendation never claims that
    an action definitely happened.
    """
    if character not in PROFILES:
        raise ValueError(f"unsupported character profile: {character}")

    ordered = sorted(events, key=lambda item: float(item.get("timestamp_s", 0.0)))
    if character == KAKASHI_PROFILE["id"]:
        return _coach_kakashi_events(ordered)
    recommendations: list[Recommendation] = []
    seen_opening = False
    hook_seen = False
    damage_since_hook = False
    last_recommendation_at = -999.0

    def add(item: Recommendation, *, min_gap: float = 0.0) -> None:
        nonlocal last_recommendation_at
        if item.timestamp_s - last_recommendation_at < min_gap:
            return
        recommendations.append(item)
        last_recommendation_at = item.timestamp_s

    for raw_event in ordered:
        event, timestamp_s, source = _event_fields(raw_event)
        if not seen_opening:
            add(_recommend(
                timestamp_s,
                "high",
                "开局中立",
                "保持中距离，先观察红圈移动；确认有安全窗口后再尝试一技能·钓星之钩。",
                "浦式的核心收益来自命中后的查克拉分支，开局盲放会把主动权交给对手。",
                0.78,
                "initial_state",
                event,
            ))
            seen_opening = True

        if event == "red_ring_state":
            add(_recommend(
                timestamp_s,
                "medium",
                "敌方位置更新",
                "用摇杆保持横向错位，等敌人进入钓钩有效距离；不要因为红圈靠近就立即交技能。",
                "红圈只能说明粗略位置，不能证明敌人正在攻击。",
                0.64,
                source,
                event,
            ), min_gap=0.45)
        elif event == "skill_1_visual_change":
            hook_seen = True
            damage_since_hook = False
            add(_recommend(
                timestamp_s,
                "high",
                "钓钩候选",
                "检查钓钩是否命中：命中则接普攻 1A-4A；未命中则立刻拉开距离，不要补第二个高风险技能。",
                "按钮变化只代表视觉候选，必须结合敌我红圈、受击闪光和血条变化确认命中。",
                0.72,
                event,
                "skill_1_region",
            ), min_gap=0.3)
        elif event == "attack_visual_change" and hook_seen:
            add(_recommend(
                timestamp_s,
                "high",
                "命中后连段窗口",
                "继续观察普攻段数；在普攻后摇确认安全时下拉摇杆，进入已夺取查克拉对应的属性终结分支。",
                "浦式的属性攻击需要先完成查克拉夺取，不能把普通普攻视觉变化直接当成属性分支。",
                0.69,
                event,
                "hook_seen",
            ), min_gap=0.25)
        elif event == "impact_or_damage_flash":
            damage_since_hook = True
            add(_recommend(
                timestamp_s,
                "medium",
                "受击候选",
                "回看这一帧确认是否命中；若命中且敌方替身可用，下一步优先骗替身或收手，不要自动延长连段。",
                "受击闪光可能来自技能特效或场景变化，不能单独证明有效伤害。",
                0.58,
                event,
            ), min_gap=0.5)
        elif event == "health_bar_change":
            priority = "high" if hook_seen and damage_since_hook else "medium"
            advice = "确认敌方血条是否下降；若下降且敌方处于低血量，保留安全收尾窗口，必要时用奥义结束。" \
                if source == "enemy_health" else "确认是否是自身掉血；若是，停止贪连段并优先拉开距离。"
            add(_recommend(
                timestamp_s,
                priority,
                "血条变化候选",
                advice,
                "血条变化是比按钮闪烁更强的结果证据，但仍需人工排除界面动画。",
                0.67,
                event,
                source,
            ), min_gap=0.4)
        elif event == "blue_ring_state":
            add(_recommend(
                timestamp_s,
                "low",
                "自身位置更新",
                "用蓝圈与红圈间距判断是否继续压进；距离不理想时先走位，不要把移动当成无条件起手。",
                "位置状态用于复盘空间关系，不直接生成摇杆方向。",
                0.61,
                event,
            ), min_gap=0.6)

    if hook_seen and not damage_since_hook:
        add(_recommend(
            ordered[-1].get("timestamp_s", 0.0) if ordered else 0.0,
            "medium",
            "钓钩结果待确认",
            "回看钓钩后的 0.5 秒：没有受击或敌方血条证据时，将这次尝试标成未命中，并记录撤退时机。",
            "把失败尝试也纳入训练集，才能学习对手的躲避习惯和浦式的风险窗口。",
            0.76,
            "hook_without_confirmation",
        ), min_gap=0.1)
    return recommendations


def _coach_kakashi_events(ordered: list[dict[str, Any]]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    seen_opening = False
    skill_2_seen = False
    attack_seen = False
    last_recommendation_at = -999.0

    def add(item: Recommendation, *, min_gap: float = 0.0) -> None:
        nonlocal last_recommendation_at
        if item.timestamp_s - last_recommendation_at < min_gap:
            return
        recommendations.append(item)
        last_recommendation_at = item.timestamp_s

    for raw_event in ordered:
        event, timestamp_s, source = _event_fields(raw_event)
        if not seen_opening:
            add(_recommend(
                timestamp_s,
                "high",
                "开局中立",
                "保持中距离，先用蓝/红圈判断 Y 轴关系；看到地面起手时优先考虑上拉 3A 躲避，不要直接交奥义。",
                "须佐卡卡西的上下特殊普攻提供不同的空间选择，开局需要先建立轴线优势。",
                0.78,
                "initial_state",
                event,
            ))
            seen_opening = True

        if event == "red_ring_state":
            add(_recommend(
                timestamp_s,
                "medium",
                "敌方轴线更新",
                "按敌方红圈位置调整 Y 轴：近身可尝试上拉 2A/3A，敌人压进时保留二技能一段虚化作为反应窗口。",
                "红圈只提供粗略位置，不能单独证明敌方已出招。",
                0.66,
                event,
                source,
            ), min_gap=0.45)
        elif event == "blue_ring_state":
            add(_recommend(
                timestamp_s,
                "low",
                "自身位置更新",
                "检查是否处于适合雷切或神威的距离；距离不足时先走位，避免特殊普攻 4A 结束后暴露。",
                "位置关系是卡卡西雷传和神威变轨是否安全的前置条件。",
                0.61,
                event,
            ), min_gap=0.6)
        elif event == "attack_visual_change":
            attack_seen = True
            add(_recommend(
                timestamp_s,
                "high",
                "普攻连段候选",
                "记录当前是普通、上拉还是下拉路线；可在 1A-4A 间混接，特殊普攻 4A 雷传后观察命中，不要默认还有安全后续。",
                "按钮视觉变化无法区分三条普攻路线，必须人工标注摇杆方向和实际段数。",
                0.71,
                event,
                "attack_region",
            ), min_gap=0.3)
        elif event == "skill_1_visual_change":
            add(_recommend(
                timestamp_s,
                "high",
                "神威·左候选",
                "如果上一段是上/下特殊 2A 或 3A，检查是否利用神威变轨改变 Y 轴；命中后记录吸入与后续连段。",
                "神威·左可以接在特殊普攻突进中，是否命中必须结合受击和位置变化确认。",
                0.73,
                event,
                "skill_1_region",
            ), min_gap=0.3)
        elif event == "skill_2_visual_change":
            skill_2_seen = True
            add(_recommend(
                timestamp_s,
                "high",
                "神威·右候选",
                "区分一段虚化和二段手里剑：一段用于观察/规避，确认敌人攻击后再考虑完美时机或接组合技；不要过早打断虚化。",
                "二技能包含虚化与投掷两个阶段，单个按钮变化不能确定当前阶段。",
                0.76,
                event,
                "skill_2_region",
            ), min_gap=0.35)
        elif event == "impact_or_damage_flash":
            add(_recommend(
                timestamp_s,
                "medium",
                "神威/雷传命中候选",
                "回看受击闪光是否与神威抓取或雷传重合；确认命中再继续连段，否则优先结束动作并回到中立。",
                "特效闪光可能来自其他技能，不能单独作为抓取成功证据。",
                0.59,
                event,
            ), min_gap=0.5)
        elif event == "health_bar_change":
            if source == "enemy_health":
                advice = "确认敌方是否进入斩杀线；血量足够低且神威手里剑命中时再用奥义·神威雷切收尾。"
                situation = "敌方血条变化"
            else:
                advice = "确认自身是否掉血；若是，停止贪连段，优先用二技能虚化或走位脱离。"
                situation = "自身血条变化"
            add(_recommend(
                timestamp_s,
                "high",
                situation,
                advice,
                "血条是收尾或撤退决策的结果证据，但仍需排除界面动画。",
                0.69,
                event,
                source,
            ), min_gap=0.45)
        elif event == "substitution_visual_change":
            add(_recommend(
                timestamp_s,
                "medium",
                "替身候选",
                "检查对手是否真的替身；若替身已交，才把神威手里剑或奥义作为下一轮压制资源，否则保留技能。",
                "替身按钮变化不等于对手已经使用替身。",
                0.63,
                event,
            ), min_gap=0.5)

    if skill_2_seen and not any(item.situation == "神威/雷传命中候选" for item in recommendations):
        add(_recommend(
            ordered[-1].get("timestamp_s", 0.0) if ordered else 0.0,
            "medium",
            "神威结果待确认",
            "回看二技能后的 0.5 秒，标注一段虚化、完美时机、二段手里剑以及是否命中；这四类状态要分开训练。",
            "卡卡西的核心不是单次技能，而是虚化、变轨、抓取和收尾之间的状态转换。",
            0.75,
            "skill_2_without_confirmation",
        ), min_gap=0.1)
    if attack_seen and not recommendations:
        add(_recommend(0.0, "low", "候选不足", "补充更多带有完整普攻段数和摇杆方向的录像。", "当前报告没有足够证据区分卡卡西的三条普攻路线。", 0.4))
    return recommendations


def build_coaching_report(report: dict[str, Any], *, character: str = "urashiki_astro_fisher") -> dict[str, Any]:
    recommendations = coach_events(report.get("events", []), character=character)
    return {
        "schema_version": "0.1",
        "mode": "offline_tactical_coach",
        "character": PROFILES[character],
        "video": report.get("video", {}),
        "source_report_event_count": len(report.get("events", [])),
        "recommendation_count": len(recommendations),
        "recommendations": [item.json() for item in recommendations],
        "notes": [
            "Suggestions are for human replay review and training only.",
            "No recommendation is a game-control command or a claim of confirmed game state.",
        ],
    }
