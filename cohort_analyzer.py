#!/usr/bin/env python3
"""Retention Cohort Analyzer — Cohort retention analysis and LTV projections."""

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


@dataclass
class Event:
    user_id: str
    event_name: str
    timestamp: datetime
    attributes: Dict[str, str]


class CohortAnalyzer:
    def __init__(self):
        self.events: List[Event] = []
        self._user_first_seen: Dict[str, datetime] = {}
        self._user_attributes: Dict[str, Dict[str, str]] = {}

    def load_csv(self, path: str, user_col: str = "user_id",
                 event_col: str = "event_name", time_col: str = "timestamp",
                 time_format: str = "%Y-%m-%d %H:%M:%S"):
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.strptime(row[time_col], time_format)
                attrs = {k: v for k, v in row.items() if k not in (user_col, event_col, time_col)}
                event = Event(
                    user_id=row[user_col],
                    event_name=row[event_col],
                    timestamp=ts,
                    attributes=attrs,
                )
                self.events.append(event)
                uid = row[user_col]
                if uid not in self._user_first_seen or ts < self._user_first_seen[uid]:
                    self._user_first_seen[uid] = ts
                self._user_attributes[uid] = attrs

        self.events.sort(key=lambda e: e.timestamp)

    def load_events(self, events: List[Dict]):
        for e in events:
            ts = e["timestamp"] if isinstance(e["timestamp"], datetime) else datetime.fromisoformat(e["timestamp"])
            event = Event(
                user_id=e["user_id"],
                event_name=e.get("event_name", "active"),
                timestamp=ts,
                attributes=e.get("attributes", {}),
            )
            self.events.append(event)
            uid = e["user_id"]
            if uid not in self._user_first_seen or ts < self._user_first_seen[uid]:
                self._user_first_seen[uid] = ts
            self._user_attributes[uid] = e.get("attributes", {})

        self.events.sort(key=lambda e: e.timestamp)

    def retention_table(self, periods: int = 12, period_type: str = "month",
                        activity: str = "any_event") -> Dict:
        # Build cohorts by signup period
        cohorts: Dict[str, set] = defaultdict(set)
        for uid, first_seen in self._user_first_seen.items():
            cohort_key = self._period_key(first_seen, period_type)
            cohorts[cohort_key].add(uid)

        # Build activity map: user -> set of active periods
        user_active_periods: Dict[str, set] = defaultdict(set)
        for event in self.events:
            if activity != "any_event" and event.event_name != activity:
                continue
            period_key = self._period_key(event.timestamp, period_type)
            user_active_periods[event.user_id].add(period_key)

        # Calculate retention rates
        sorted_cohorts = sorted(cohorts.keys())
        all_periods = sorted(set(
            self._period_key(e.timestamp, period_type) for e in self.events
        ))

        table = {}
        for cohort in sorted_cohorts:
            users = cohorts[cohort]
            cohort_idx = all_periods.index(cohort) if cohort in all_periods else -1
            if cohort_idx < 0:
                continue

            retention = {}
            for offset in range(periods + 1):
                period_idx = cohort_idx + offset
                if period_idx >= len(all_periods):
                    break
                period = all_periods[period_idx]
                active = sum(1 for u in users if period in user_active_periods[u])
                retention[offset] = active / len(users) if users else 0

            table[cohort] = {"users": len(users), "retention": retention}

        return {"cohorts": table, "periods": periods, "period_type": period_type}

    def project_ltv(self, retention_data: Dict, arpu_per_period: float,
                    discount_rate: float = 0.10, projection_months: int = 36) -> Dict:
        # Average retention curve across all cohorts
        cohorts = retention_data["cohorts"]
        max_period = max(
            max(c["retention"].keys()) for c in cohorts.values() if c["retention"]
        )

        avg_retention = {}
        for p in range(max_period + 1):
            rates = [c["retention"][p] for c in cohorts.values() if p in c["retention"]]
            avg_retention[p] = sum(rates) / len(rates) if rates else 0

        # Project forward using power law decay
        if max_period >= 2 and avg_retention.get(max_period, 0) > 0:
            # Simple projection: last known rate decays at observed rate
            decay_rate = avg_retention[max_period] / avg_retention.get(max(1, max_period - 1), 1)
            for p in range(max_period + 1, projection_months + 1):
                projected = avg_retention[max_period] * (decay_rate ** (p - max_period))
                avg_retention[p] = max(0, projected)

        # Calculate LTV
        monthly_discount = (1 + discount_rate) ** (1 / 12) - 1
        ltv = 0
        for p in range(projection_months + 1):
            rate = avg_retention.get(p, 0)
            discounted = arpu_per_period * rate / ((1 + monthly_discount) ** p)
            ltv += discounted

        # Payback period
        cumulative = 0
        payback = None
        for p in range(projection_months + 1):
            rate = avg_retention.get(p, 0)
            cumulative += arpu_per_period * rate
            if cumulative >= arpu_per_period / avg_retention.get(0, 1) and payback is None:
                payback = p

        return {
            "ltv": ltv,
            "arpu_per_period": arpu_per_period,
            "retention_m12": avg_retention.get(12, 0),
            "payback_months": payback or 0,
            "avg_retention": avg_retention,
        }

    def compare_segments(self, segment_key: str, periods: int = 6,
                         period_type: str = "month") -> Dict:
        # Group users by segment
        segments: Dict[str, set] = defaultdict(set)
        for uid, attrs in self._user_attributes.items():
            seg = attrs.get(segment_key, "unknown")
            segments[seg].add(uid)

        results = {}
        for seg_name, seg_users in segments.items():
            # Filter events to segment users
            seg_events = [e for e in self.events if e.user_id in seg_users]
            if not seg_events:
                continue

            sub = CohortAnalyzer()
            sub.events = seg_events
            sub._user_first_seen = {u: t for u, t in self._user_first_seen.items() if u in seg_users}
            sub._user_attributes = {u: a for u, a in self._user_attributes.items() if u in seg_users}

            table = sub.retention_table(periods=periods, period_type=period_type)
            results[seg_name] = {"users": len(seg_users), "table": table}

        return results

    def print_table(self, data: Dict):
        cohorts = data["cohorts"]
        periods = data["periods"]
        period_prefix = "M" if data["period_type"] == "month" else "W"

        header = f"{'Cohort':<12} {'Users':>6}  "
        header += "  ".join(f"{period_prefix}{i:<3}" for i in range(min(periods + 1, 8)))
        print(f"\n  {header}")
        print(f"  {'─' * len(header)}")

        for cohort in sorted(cohorts.keys()):
            c = cohorts[cohort]
            row = f"  {cohort:<12} {c['users']:>6}  "
            for p in range(min(periods + 1, 8)):
                if p in c["retention"]:
                    row += f"{c['retention'][p]:>5.0%}  "
                else:
                    row += "       "
            print(row)
        print()

    @staticmethod
    def _period_key(dt: datetime, period_type: str) -> str:
        if period_type == "month":
            return dt.strftime("%Y-%m")
        elif period_type == "week":
            return dt.strftime("%Y-W%W")
        else:
            return dt.strftime("%Y-%m-%d")


def demo():
    import random
    random.seed(42)

    analyzer = CohortAnalyzer()

    # Generate synthetic events
    events = []
    base_date = datetime(2025, 7, 1)
    user_counter = 0

    for month_offset in range(7):
        cohort_start = base_date + timedelta(days=month_offset * 30)
        cohort_size = random.randint(1800, 2700)

        for _ in range(cohort_size):
            user_counter += 1
            uid = f"user_{user_counter:05d}"
            channels = ["organic", "paid_search", "referral"]
            channel = random.choices(channels, weights=[45, 35, 20])[0]

            # Signup event
            signup_time = cohort_start + timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
            events.append({
                "user_id": uid,
                "event_name": "signup",
                "timestamp": signup_time,
                "attributes": {"acquisition_channel": channel},
            })

            # Simulate activity with realistic decay
            retention_probs = {
                "organic": [1, 0.72, 0.55, 0.48, 0.44, 0.41, 0.39, 0.38],
                "paid_search": [1, 0.61, 0.42, 0.35, 0.30, 0.28, 0.26, 0.25],
                "referral": [1, 0.78, 0.62, 0.55, 0.51, 0.49, 0.47, 0.46],
            }
            probs = retention_probs[channel]

            for future_month in range(1, 8):
                if future_month >= len(probs):
                    break
                if random.random() < probs[future_month]:
                    activity_time = signup_time + timedelta(days=future_month * 30 + random.randint(0, 29))
                    events.append({
                        "user_id": uid,
                        "event_name": "active",
                        "timestamp": activity_time,
                        "attributes": {"acquisition_channel": channel},
                    })

    analyzer.load_events(events)
    table = analyzer.retention_table(periods=7)
    analyzer.print_table(table)

    ltv = analyzer.project_ltv(table, arpu_per_period=29.99)
    print(f"  LTV Projection")
    print(f"  {'=' * 35}")
    print(f"  ARPU/month:      ${ltv['arpu_per_period']:.2f}")
    print(f"  Projected LTV:   ${ltv['ltv']:.2f}")
    print(f"  Payback period:  {ltv['payback_months']} months")
    print()


if __name__ == "__main__":
    demo()
