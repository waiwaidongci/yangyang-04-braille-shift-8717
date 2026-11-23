"""Exact randomization inference for the braille embossing pilot."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import combinations, product
from math import comb, lcm
from statistics import mean

CONTROL = "现行参数"
TRIAL = "试验参数"
MAX_ASSIGNMENTS = 200_000


def _number(value, label, low, high, *, integer=False):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}必须是有效数字。") from None
    if not number.is_finite() or not low <= number <= high:
        raise ValueError(f"{label}必须在 {low} 到 {high} 之间。")
    if integer and number != number.to_integral_value():
        raise ValueError(f"{label}必须为整数。")
    return int(number) if integer else Fraction(number)


def _text(row, key, label):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"请填写{label}。")
    return value.strip()


def _parse(row):
    ticket = _text(row, "ticket", "工票编号")
    team = _text(row, "team", "班组")
    arm = row.get("arm")
    if arm not in (CONTROL, TRIAL):
        raise ValueError(f"工票 {ticket} 的参数组必须为现行参数或试验参数。")
    work_date = _text(row, "work_date", "压印日期")
    try:
        if date.fromisoformat(work_date).isoformat() != work_date:
            raise ValueError
    except ValueError:
        raise ValueError(f"工票 {ticket} 的压印日期必须采用 YYYY-MM-DD 格式。") from None
    seconds = _number(row.get("seconds"), f"工票 {ticket} 的百张压印耗时（秒）", 1, 7200)
    checked = _number(row.get("checked_dots"), f"工票 {ticket} 的抽检点数", 1, 1_000_000, integer=True)
    errors = _number(row.get("error_dots"), f"工票 {ticket} 的错点数", 0, 1_000_000, integer=True)
    if errors > checked:
        raise ValueError(f"工票 {ticket} 的错点数不能超过抽检点数。")
    return ticket, team, arm, seconds, checked, errors


def validate(row: dict):
    _parse(row)


def _parse_assignment(row):
    team = _text(row, "team", "班组")
    machine = _text(row, "machine", "机型")
    arm = row.get("arm")
    if arm not in (CONTROL, TRIAL):
        raise ValueError(f"班组 {team} 的分派参数必须为现行参数或试验参数。")
    return team, machine, arm


def validate_assignment(row: dict):
    _parse_assignment(row)


def seed() -> list[dict]:
    layout = [
        ("压印一班", CONTROL, 764, 5, 9),
        ("压印二班", CONTROL, 748, 6, 8),
        ("压印三班", CONTROL, 781, 7, 11),
        ("压印四班", CONTROL, 759, 8, 10),
        ("压印五班", TRIAL, 658, 8, 10),
        ("压印六班", TRIAL, 675, 7, 12),
        ("压印七班", TRIAL, 689, 6, 11),
        ("压印八班", TRIAL, 667, 5, 13),
    ]
    first_day = date(2026, 11, 9)
    return [
        {
            "ticket": f"CY-2611-{number:02d}-{job + 1:02d}",
            "team": team,
            "arm": arm,
            "work_date": (first_day + timedelta(days=job)).isoformat(),
            "seconds": center + (2 * job - jobs + 1) * (3 + number % 3),
            "checked_dots": 2500,
            "error_dots": error_base + job % 3 - 1,
        }
        for number, (team, arm, center, jobs, error_base) in enumerate(layout, start=1)
        for job in range(jobs)
    ]


def seed_assignments() -> list[dict]:
    """First-round assignment sheet: randomization stratified by machine model."""
    layout = [
        ("压印一班", "平压式", CONTROL),
        ("压印二班", "平压式", CONTROL),
        ("压印五班", "平压式", TRIAL),
        ("压印六班", "平压式", TRIAL),
        ("压印三班", "圆压式", CONTROL),
        ("压印四班", "圆压式", CONTROL),
        ("压印七班", "圆压式", TRIAL),
        ("压印八班", "圆压式", TRIAL),
    ]
    return [{"team": team, "machine": machine, "arm": arm} for team, machine, arm in layout]


def _randomization_test(control_means, trial_means):
    """Count ties in the one-sided tail with exact integer arithmetic."""
    cluster_count = len(control_means) + len(trial_means)
    size = min(len(control_means), len(trial_means))
    assignments = comb(cluster_count, size)
    if assignments > MAX_ASSIGNMENTS:
        raise ValueError(f"固定组规模有 {assignments:,} 种分派，超过精确枚举上限 {MAX_ASSIGNMENTS:,}。")

    # With a fixed group size, larger control-minus-trial differences correspond
    # to smaller trial sums or larger control sums. Enumerate the smaller arm.
    trial_is_smaller = len(trial_means) <= len(control_means)
    selected, other = (trial_means, control_means) if trial_is_smaller else (control_means, trial_means)
    direction = 1 if trial_is_smaller else -1
    scale = lcm(*(value.denominator for value in selected + other))
    scores = [direction * value.numerator * (scale // value.denominator) for value in selected + other]
    observed = sum(scores[:size])
    extreme = sum(sum(candidate) <= observed for candidate in combinations(scores, size))
    return Fraction(extreme, assignments), extreme, assignments


def _stratified_test(strata):
    """One-sided exact p-value when randomization is stratified by machine model.

    Each stratum keeps the two group sizes planned on the assignment sheet, and
    the reference set is the product of per-stratum labelings. With equal team
    weights the saving (control mean − trial mean) shrinks exactly when the sum
    of trial team means grows, so count labelings whose trial sum does not
    exceed the observed one, ties included.
    """
    total = 1
    plans = []
    for members in strata:
        trial_size = sum(arm == TRIAL for _, arm in members)
        total *= comb(len(members), trial_size)
        plans.append((members, trial_size))
    if total > MAX_ASSIGNMENTS:
        raise ValueError(f"按机型分层固定原定班组数有 {total:,} 种分派，超过精确枚举上限 {MAX_ASSIGNMENTS:,}。")
    scale = lcm(*(value.denominator for members, _ in plans for value, _ in members))
    observed = 0
    strata_sums = []
    for members, trial_size in plans:
        scaled = [int(value * scale) for value, _ in members]
        observed += sum(value for value, (_, arm) in zip(scaled, members) if arm == TRIAL)
        strata_sums.append([sum(pick) for pick in combinations(scaled, trial_size)])
    extreme = sum(sum(candidate) <= observed for candidate in product(*strata_sums))
    return Fraction(extreme, total), extreme, total


def analyze(rows: list[dict], parameters: dict) -> dict:
    alpha = _number(parameters.get("alpha", 0.05), "单侧显著性水平", 0.001, 0.2)
    minimum_gain = _number(parameters.get("min_gain_seconds", 60), "最低节省耗时（秒）", 0, 7200)
    quality_limit = _number(parameters.get("max_error_pct", 0.5), "试验组错点率上限（%）", 0, 100)

    jobs_by_team = defaultdict(list)
    arm_by_team = {}
    tickets = set()
    for row in rows:
        ticket, team, arm, seconds, checked, errors = _parse(row)
        if ticket in tickets:
            raise ValueError(f"工票编号 {ticket} 重复，请核对合并记录。")
        tickets.add(ticket)
        if arm_by_team.setdefault(team, arm) != arm:
            raise ValueError(f"班组 {team} 同时出现在两种参数组，请核对原始随机分派表。")
        jobs_by_team[team].append((seconds, checked, errors))

    arm_means = {CONTROL: [], TRIAL: []}
    arm_checked = {CONTROL: 0, TRIAL: 0}
    arm_errors = {CONTROL: 0, TRIAL: 0}
    detail = []
    quality_review = []
    for team in sorted(jobs_by_team, key=lambda name: (arm_by_team[name] == TRIAL, name)):
        jobs = jobs_by_team[team]
        arm = arm_by_team[team]
        seconds, checked, errors = zip(*jobs)
        team_mean = mean(seconds)
        checked_count, error_count = sum(checked), sum(errors)
        arm_means[arm].append(team_mean)
        arm_checked[arm] += checked_count
        arm_errors[arm] += error_count
        error_pct = Fraction(100 * error_count, checked_count)
        if arm == TRIAL and error_pct > quality_limit:
            quality_review.append(team)
        detail.append({
            "team": team,
            "arm": arm,
            "job_count": len(jobs),
            "mean_seconds": round(float(team_mean), 2),
            "checked_dots": checked_count,
            "error_dots": error_count,
            "error_pct": round(float(error_pct), 4),
        })

    control_means, trial_means = arm_means[CONTROL], arm_means[TRIAL]
    if min(len(control_means), len(trial_means)) < 2:
        raise ValueError("现行参数组和试验参数组各需至少 2 个有有效工票的独立班组。")
    p_value, extreme, assignments = _randomization_test(control_means, trial_means)
    control_mean, trial_mean = mean(control_means), mean(trial_means)
    gain = control_mean - trial_mean
    control_error, trial_error = (
        Fraction(100 * arm_errors[arm], arm_checked[arm]) for arm in (CONTROL, TRIAL)
    )
    blockers = []
    if p_value > alpha:
        blockers.append("压印提速证据未达到单侧显著性门槛")
    if gain < minimum_gain:
        blockers.append("每百张节省耗时低于放行门槛")
    if trial_error > quality_limit:
        blockers.append("试验组错点率超过护栏")

    if blockers:
        headline = "暂缓放行"
        recommendation = "。".join(blockers) + "。请主管保留现行参数，由工艺员按班组复查工票和抽检记录。"
    else:
        headline = "建议限量放行"
        recommendation = "提速证据、节省耗时和错点率均通过门槛。建议主管安排下一班次限量试产并持续抽检。"
    if quality_review:
        recommendation += "请优先复查超出同一错点率阈值的班组：" + "、".join(quality_review) + "。"
    return {
        "headline": headline,
        "summary": recommendation + "本次推断依赖班组完全随机分派，错点率用于本次抽检的描述性护栏。",
        "metrics": [
            {"label": "有效工票", "value": len(tickets), "unit": "张"},
            {"label": "试验组 / 现行组班组数", "value": f"{len(trial_means)} / {len(control_means)}"},
            {"label": "试验参数节省耗时", "value": round(float(gain), 4), "unit": "秒/百张"},
            {"label": "单侧精确 p 值", "value": float(p_value)},
            {"label": "至少同样有利的分派 / 全部分派", "value": f"{extreme} / {assignments}"},
            {"label": "现行组错点率", "value": round(float(control_error), 4), "unit": "%"},
            {"label": "试验组错点率", "value": round(float(trial_error), 4), "unit": "%"},
        ],
        "columns": [
            {"key": "team", "label": "班组"},
            {"key": "arm", "label": "参数组"},
            {"key": "job_count", "label": "有效工票（张）"},
            {"key": "mean_seconds", "label": "平均压印耗时（秒/百张）"},
            {"key": "checked_dots", "label": "抽检点数（点）"},
            {"key": "error_dots", "label": "错点数（点）"},
            {"key": "error_pct", "label": "错点率（%）"},
        ],
        "rows": detail,
        "chart": {
            "label": "班组等权的平均压印耗时",
            "unit": "秒/百张",
            "points": [
                {"label": CONTROL, "value": round(float(control_mean), 2)},
                {"label": TRIAL, "value": round(float(trial_mean), 2)},
            ],
        },
    }


def analyze_stratified(rows: list[dict], sheet: list[dict], parameters: dict) -> dict:
    """Reconcile tickets with the assignment sheet, then test within machine strata."""
    alpha = _number(parameters.get("alpha", 0.05), "单侧显著性水平", 0.001, 0.2)
    minimum_gain = _number(parameters.get("min_gain_seconds", 60), "最低节省耗时（秒）", 0, 7200)
    quality_limit = _number(parameters.get("max_error_pct", 0.5), "试验组错点率上限（%）", 0, 100)

    assignments = {}
    for entry in sheet:
        team, machine, arm = _parse_assignment(entry)
        if team in assignments:
            raise ValueError(f"分派依据中班组 {team} 出现多次，请核对分派订正记录。")
        assignments[team] = (machine, arm)
    if not assignments:
        raise ValueError("分派依据为空，请先登记班组随机分派表。")

    tickets = set()
    jobs_by_team = defaultdict(list)
    for row in rows:
        ticket, team, arm, seconds, checked, errors = _parse(row)
        if ticket in tickets:
            raise ValueError(f"工票编号 {ticket} 重复，请核对合并记录。")
        tickets.add(ticket)
        jobs_by_team[team].append((arm, seconds, checked, errors))

    differences = []
    for team in sorted(set(jobs_by_team) - set(assignments)):
        differences.append({
            "team": team,
            "issue": "未在分派表",
            "detail": f"{len(jobs_by_team[team])} 张工票来自分派表外班组，本次分析未纳入。",
        })
    aligned = {}
    for team in sorted(assignments):
        machine, arm = assignments[team]
        jobs = jobs_by_team.get(team) or []
        if not jobs:
            differences.append({
                "team": team,
                "issue": "缺班",
                "detail": f"分派为{machine}·{arm}，但没有有效工票，本次分析未纳入。",
            })
            continue
        conflicts = sum(recorded != arm for recorded, _, _, _ in jobs)
        if conflicts:
            differences.append({
                "team": team,
                "issue": "分派冲突",
                "detail": f"{conflicts} 张工票登记的参数组与分派表「{arm}」不一致，按分派表对齐。",
            })
        aligned[team] = (machine, arm, [(seconds, checked, errors) for _, seconds, checked, errors in jobs])
    if not aligned:
        raise ValueError("分派表与工票没有可对齐的班组，请核对两份依据。")

    arm_means = {CONTROL: [], TRIAL: []}
    arm_checked = {CONTROL: 0, TRIAL: 0}
    arm_errors = {CONTROL: 0, TRIAL: 0}
    strata = defaultdict(list)
    detail = []
    quality_review = []
    for team in sorted(aligned, key=lambda name: (aligned[name][0], aligned[name][1] == TRIAL, name)):
        machine, arm, jobs = aligned[team]
        seconds, checked, errors = zip(*jobs)
        team_mean = mean(seconds)
        checked_count, error_count = sum(checked), sum(errors)
        arm_means[arm].append(team_mean)
        arm_checked[arm] += checked_count
        arm_errors[arm] += error_count
        strata[machine].append((team_mean, arm))
        error_pct = Fraction(100 * error_count, checked_count)
        if arm == TRIAL and error_pct > quality_limit:
            quality_review.append(team)
        detail.append({
            "machine": machine,
            "team": team,
            "arm": arm,
            "job_count": len(jobs),
            "mean_seconds": round(float(team_mean), 2),
            "checked_dots": checked_count,
            "error_dots": error_count,
            "error_pct": round(float(error_pct), 4),
        })

    control_means, trial_means = arm_means[CONTROL], arm_means[TRIAL]
    if min(len(control_means), len(trial_means)) < 2:
        raise ValueError("现行参数组和试验参数组各需至少 2 个与分派表对齐的班组。")
    p_value, extreme, total = _stratified_test(list(strata.values()))
    control_mean, trial_mean = mean(control_means), mean(trial_means)
    gain = control_mean - trial_mean
    control_error, trial_error = (
        Fraction(100 * arm_errors[arm], arm_checked[arm]) for arm in (CONTROL, TRIAL)
    )
    blockers = []
    if p_value > alpha:
        blockers.append("压印提速证据未达到单侧显著性门槛")
    if gain < minimum_gain:
        blockers.append("每百张节省耗时低于放行门槛")
    if trial_error > quality_limit:
        blockers.append("试验组错点率超过护栏")

    if blockers:
        headline = "暂缓放行"
        recommendation = "。".join(blockers) + "。请主管保留现行参数，由工艺员按班组复查工票和抽检记录。"
    else:
        headline = "建议限量放行"
        recommendation = "提速证据、节省耗时和错点率均通过门槛。建议主管安排下一班次限量试产并持续抽检。"
    if quality_review:
        recommendation += "请优先复查超出同一错点率阈值的班组：" + "、".join(quality_review) + "。"
    if differences:
        recommendation += f"分派对账列出 {len(differences)} 项差异，已按分派表对齐后计算。"
    else:
        recommendation += "分派表与工票对账一致。"
    return {
        "headline": headline,
        "summary": recommendation + "本次推断按机型分层固定原定班组数做精确随机化检验，错点率用于本次抽检的描述性护栏。",
        "metrics": [
            {"label": "有效工票", "value": sum(row["job_count"] for row in detail), "unit": "张"},
            {"label": "参与机型", "value": len(strata), "unit": "个"},
            {"label": "试验组 / 现行组班组数", "value": f"{len(trial_means)} / {len(control_means)}"},
            {"label": "试验参数节省耗时", "value": round(float(gain), 4), "unit": "秒/百张"},
            {"label": "单侧精确 p 值", "value": float(p_value)},
            {"label": "至少同样有利的分派 / 全部分派", "value": f"{extreme} / {total}"},
            {"label": "现行组错点率", "value": round(float(control_error), 4), "unit": "%"},
            {"label": "试验组错点率", "value": round(float(trial_error), 4), "unit": "%"},
            {"label": "分派对账差异", "value": len(differences), "unit": "项"},
        ],
        "columns": [
            {"key": "machine", "label": "机型"},
            {"key": "team", "label": "班组"},
            {"key": "arm", "label": "参数组"},
            {"key": "job_count", "label": "有效工票（张）"},
            {"key": "mean_seconds", "label": "平均压印耗时（秒/百张）"},
            {"key": "checked_dots", "label": "抽检点数（点）"},
            {"key": "error_dots", "label": "错点数（点）"},
            {"key": "error_pct", "label": "错点率（%）"},
        ],
        "rows": detail,
        "reconciliation": differences,
        "chart": {
            "label": "班组等权的平均压印耗时",
            "unit": "秒/百张",
            "points": [
                {"label": CONTROL, "value": round(float(control_mean), 2)},
                {"label": TRIAL, "value": round(float(trial_mean), 2)},
            ],
        },
    }
