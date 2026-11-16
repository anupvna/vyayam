"""Body tracking: weigh-ins, measurements, and a summary for the Progress tab.

Logging a weigh-in for the latest day also updates the profile's current weight,
so goal checks and the setup summary stay current.
"""

from datetime import date
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator

from app.auth.deps import CurrentUser, csrf_user, current_user, get_conn
from app.engine.body import (
    navy_body_fat,
    project,
    rate_advice,
    recent_rate,
    slope_per_week,
    trend_weights,
)
from app.engine.goals import MIN_HEALTHY_BMI, bmi

router = APIRouter(prefix="/body", tags=["body"])

MEASURES = ("neck_cm", "waist_cm", "hips_cm", "chest_cm", "arm_cm", "thigh_cm")


class WeightIn(BaseModel):
    weight_kg: float = Field(ge=30, le=300)


class MeasurementsIn(BaseModel):
    neck_cm: float | None = Field(default=None, ge=10, le=100)
    waist_cm: float | None = Field(default=None, ge=30, le=250)
    hips_cm: float | None = Field(default=None, ge=30, le=250)
    chest_cm: float | None = Field(default=None, ge=30, le=250)
    arm_cm: float | None = Field(default=None, ge=10, le=100)
    thigh_cm: float | None = Field(default=None, ge=20, le=150)
    body_fat_pct: float | None = Field(default=None, ge=3, le=60)
    body_fat_source: Literal["scale", "dexa", "other"] | None = None

    @model_validator(mode="after")
    def _something(self) -> "MeasurementsIn":
        if all(getattr(self, k) is None for k in (*MEASURES, "body_fat_pct")):
            raise ValueError("enter at least one measurement")
        if self.body_fat_pct is not None and self.body_fat_source is None:
            self.body_fat_source = "other"
        return self


class WeightPoint(BaseModel):
    day: date
    weight_kg: float
    trend_kg: float


class FatPoint(BaseModel):
    day: date
    pct: float
    method: str  # "navy estimate" or the device used


class MeasurementPoint(MeasurementsIn):
    day: date

    @model_validator(mode="after")
    def _something(self) -> "MeasurementPoint":  # stored rows are always valid
        return self


class ProjectionOut(BaseModel):
    status: str
    message: str
    earliest: date | None
    latest: date | None
    target: float
    unit: str


class BodySummary(BaseModel):
    weights: list[WeightPoint]
    latest_weight_kg: float | None
    trend_kg: float | None
    rate_kg_per_week: float | None
    bmi: float | None
    bmi_note: str
    body_fat: list[FatPoint]
    measurements: list[MeasurementPoint]
    weight_projection: ProjectionOut | None
    body_fat_projection: ProjectionOut | None
    advice: list[str]


@router.put("/weights/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def log_weight(
    day: date,
    body: WeightIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    async with conn.transaction():
        await conn.execute(
            """INSERT INTO body_weights (user_id, day, weight_kg) VALUES ($1, $2, $3)
               ON CONFLICT (user_id, day) DO UPDATE SET weight_kg = EXCLUDED.weight_kg,
               updated_at = now()""",
            user.id,
            day,
            body.weight_kg,
        )
        latest = await conn.fetchval(
            "SELECT max(day) FROM body_weights WHERE user_id = $1", user.id
        )
        if latest == day:
            await conn.execute(
                "UPDATE profiles SET weight_kg = $2, updated_at = now() WHERE user_id = $1",
                user.id,
                body.weight_kg,
            )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/weights/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_weight(
    day: date,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute("DELETE FROM body_weights WHERE user_id = $1 AND day = $2", user.id, day)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/measurements/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def log_measurements(
    day: date,
    body: MeasurementsIn,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    cols = [*MEASURES, "body_fat_pct", "body_fat_source"]
    values = [getattr(body, c) for c in cols]
    await conn.execute(
        f"""INSERT INTO body_measurements (user_id, day, {", ".join(cols)})
            VALUES ($1, $2, {", ".join(f"${i}" for i in range(3, len(cols) + 3))})
            ON CONFLICT (user_id, day) DO UPDATE SET
            {", ".join(f"{c} = EXCLUDED.{c}" for c in cols)}, updated_at = now()""",
        user.id,
        day,
        *values,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/measurements/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_measurements(
    day: date,
    user: CurrentUser = Depends(csrf_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> Response:
    await conn.execute(
        "DELETE FROM body_measurements WHERE user_id = $1 AND day = $2", user.id, day
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _projection(p, target: float, unit: str) -> ProjectionOut:
    return ProjectionOut(
        status=p.status,
        message=p.message,
        earliest=p.earliest,
        latest=p.latest,
        target=target,
        unit=unit,
    )


@router.get("/summary", response_model=BodySummary)
async def summary(
    today: date,
    user: CurrentUser = Depends(current_user),
    conn: asyncpg.Connection = Depends(get_conn),
) -> BodySummary:
    profile = await conn.fetchrow(
        """SELECT sex, height_cm, weight_kg, target_weight_kg, target_body_fat_pct
           FROM profiles WHERE user_id = $1""",
        user.id,
    )
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finish setup first")

    rows = await conn.fetch(
        "SELECT day, weight_kg FROM body_weights WHERE user_id = $1 AND day <= $2 ORDER BY day",
        user.id,
        today,
    )
    trend = trend_weights([(r["day"], r["weight_kg"]) for r in rows])
    rate = recent_rate(trend, today)
    latest = trend[-1][1] if trend else None
    current_trend = trend[-1][2] if trend else None
    weight_now = current_trend or profile["weight_kg"]

    m_rows = await conn.fetch(
        "SELECT * FROM body_measurements WHERE user_id = $1 AND day <= $2 ORDER BY day",
        user.id,
        today,
    )
    measurements = [
        MeasurementPoint(
            day=r["day"], **{k: r[k] for k in (*MEASURES, "body_fat_pct", "body_fat_source")}
        )
        for r in m_rows
    ]
    fat: list[FatPoint] = []
    for r in m_rows:
        if r["body_fat_pct"] is not None:
            fat.append(FatPoint(day=r["day"], pct=r["body_fat_pct"], method=r["body_fat_source"]))
        elif r["neck_cm"] and r["waist_cm"]:
            pct = navy_body_fat(
                profile["sex"], profile["height_cm"], r["neck_cm"], r["waist_cm"], r["hips_cm"]
            )
            if pct is not None:
                fat.append(FatPoint(day=r["day"], pct=pct, method="navy estimate"))

    weight_proj = None
    if profile["target_weight_kg"] is not None:
        if trend:
            weight_proj = _projection(
                project(weight_now, profile["target_weight_kg"], rate, today),
                profile["target_weight_kg"],
                "kg",
            )
        else:
            weight_proj = ProjectionOut(
                status="not_enough_data",
                message="Log your weight a few times a week to see when you'll reach your target.",
                earliest=None,
                latest=None,
                target=profile["target_weight_kg"],
                unit="kg",
            )
    fat_proj = None
    if profile["target_body_fat_pct"] is not None and fat:
        fat_rate = slope_per_week([(f.day, f.pct) for f in fat if (today - f.day).days <= 42])
        fat_proj = _projection(
            project(fat[-1].pct, profile["target_body_fat_pct"], fat_rate, today, "%"),
            profile["target_body_fat_pct"],
            "%",
        )

    value = round(bmi(weight_now, profile["height_cm"]), 1)
    note = (
        "BMI doesn't know muscle from fat: muscular people often read 'overweight'. "
        "Use it alongside waist and body fat, not alone."
    )
    if value < MIN_HEALTHY_BMI:
        note = (
            "Your BMI is below the healthy range (18.5). "
            "If you're losing weight, consider eating at maintenance."
        )
    return BodySummary(
        weights=[WeightPoint(day=d, weight_kg=w, trend_kg=round(t, 2)) for d, w, t in trend],
        latest_weight_kg=latest,
        trend_kg=round(current_trend, 2) if current_trend else None,
        rate_kg_per_week=round(rate, 2) if rate is not None else None,
        bmi=value,
        bmi_note=note,
        body_fat=fat,
        measurements=measurements,
        weight_projection=weight_proj,
        body_fat_projection=fat_proj,
        advice=rate_advice(rate, weight_now),
    )
