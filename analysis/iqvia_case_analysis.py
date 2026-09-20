from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


SEED = 20260919
RNG = np.random.default_rng(SEED)
COLORS = {
    "navy": "#15324B",
    "blue": "#2F6B8A",
    "teal": "#1C8A87",
    "gold": "#D5A021",
    "red": "#B54A4A",
    "green": "#4F8A5B",
    "gray": "#687780",
    "light": "#EAF0F3",
    "ink": "#1F2933",
}


def safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return None
    return float(value)


def json_clean(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return json_clean(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return safe_float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibrib.ttf" if bold else r"C:\Windows\Fonts\calibri.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def fmt_units(x: float) -> str:
    ax = abs(x)
    if ax >= 1e9:
        return f"{x/1e9:.1f}B"
    if ax >= 1e6:
        return f"{x/1e6:.1f}M"
    if ax >= 1e3:
        return f"{x/1e3:.1f}K"
    return f"{x:.0f}"


def nice_ticks(vmin: float, vmax: float, n: int = 5) -> list[float]:
    if not np.isfinite(vmin) or not np.isfinite(vmax):
        return [0.0, 1.0]
    if math.isclose(vmin, vmax):
        pad = abs(vmin) * 0.2 + 1.0
        vmin, vmax = vmin - pad, vmax + pad
    span = max(vmax - vmin, 1e-12)
    raw = span / max(n - 1, 1)
    mag = 10 ** math.floor(math.log10(raw))
    residual = raw / mag
    step = (1 if residual <= 1 else 2 if residual <= 2 else 5 if residual <= 5 else 10) * mag
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    return list(np.arange(lo, hi + step * 0.5, step))


def draw_title(draw: ImageDraw.ImageDraw, title: str, subtitle: str | None = None) -> None:
    draw.text((90, 50), title, fill=COLORS["navy"], font=get_font(34, True))
    if subtitle:
        draw.text((90, 100), subtitle, fill=COLORS["gray"], font=get_font(19))


def save_annual_sales_chart(annual: pd.DataFrame, path: Path) -> None:
    w, h = 1600, 900
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    draw_title(d, "Portfolio unit sales peaked in 2021, then reset lower", "Annual pack-equivalent units in the 20-INN development sample")
    left, top, right, bottom = 150, 185, 1490, 740
    vals = annual["sales"].to_numpy(float)
    years = annual["year"].astype(str).tolist()
    ymax = max(nice_ticks(0, vals.max(), 6))
    ticks = nice_ticks(0, ymax, 6)
    for t in ticks:
        y = bottom - (t / ymax) * (bottom - top)
        d.line((left, y, right, y), fill="#D9E1E5", width=2)
        d.text((left - 95, y - 12), fmt_units(t), fill=COLORS["gray"], font=get_font(17))
    bar_gap = (right - left) / len(vals)
    bw = bar_gap * 0.55
    for i, (year, value) in enumerate(zip(years, vals)):
        x = left + bar_gap * (i + 0.5)
        y = bottom - (value / ymax) * (bottom - top)
        color = COLORS["teal"] if i < 3 else COLORS["blue"]
        d.rounded_rectangle((x - bw/2, y, x + bw/2, bottom), radius=8, fill=color)
        d.text((x - 24, bottom + 20), year, fill=COLORS["ink"], font=get_font(20, True))
        label = fmt_units(value)
        box = d.textbbox((0, 0), label, font=get_font(20, True))
        d.text((x - (box[2]-box[0])/2, y - 36), label, fill=COLORS["navy"], font=get_font(20, True))
    d.text((90, 830), "Source: Teva development sample; values represent unit/pack demand, not revenue.", fill=COLORS["gray"], font=get_font(16))
    img.save(path)


def save_model_bars(rows: list[dict[str, Any]], metric: str, title: str, path: Path, percent: bool = False) -> None:
    w, h = 1600, 900
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    draw_title(d, title, "Out-of-time test period")
    rows = sorted(rows, key=lambda r: r[metric])
    labels = [str(r["model"]) for r in rows]
    vals = np.array([float(r[metric]) for r in rows])
    left, top, right, bottom = 430, 180, 1450, 760
    xmax = max(nice_ticks(0, vals.max() * 1.05, 6))
    for t in nice_ticks(0, xmax, 6):
        x = left + t / xmax * (right-left)
        d.line((x, top, x, bottom), fill="#E2E8EC", width=2)
        lab = f"{t:.0%}" if percent else f"{t:.2f}"
        d.text((x-24, bottom+18), lab, fill=COLORS["gray"], font=get_font(16))
    band = (bottom-top)/len(rows)
    palette = [COLORS["teal"], COLORS["blue"], COLORS["gold"], COLORS["gray"], COLORS["red"]]
    for i, (lab, value) in enumerate(zip(labels, vals)):
        y = top + band*(i+0.5)
        d.text((90, y-14), lab, fill=COLORS["ink"], font=get_font(19, True))
        x2 = left + value/xmax*(right-left)
        d.rounded_rectangle((left, y-18, x2, y+18), radius=8, fill=palette[i % len(palette)])
        txt = f"{value:.1%}" if percent else f"{value:.2f}"
        d.text((x2+15, y-14), txt, fill=COLORS["navy"], font=get_font(19, True))
    img.save(path)


def save_forecast_chart(actual: pd.DataFrame, predictions: dict[str, np.ndarray], path: Path) -> None:
    w, h = 1600, 900
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    draw_title(d, "2023 portfolio demand: actual versus out-of-time forecasts", "Monthly portfolio pack-equivalent units")
    left, top, right, bottom = 145, 190, 1490, 725
    actual_vals = actual["sales"].to_numpy(float)
    all_vals = [actual_vals] + [np.asarray(v, float) for v in predictions.values()]
    ymin, ymax = min(v.min() for v in all_vals), max(v.max() for v in all_vals)
    ticks = nice_ticks(ymin*0.92, ymax*1.08, 6)
    ymin, ymax = min(ticks), max(ticks)
    for t in ticks:
        y = bottom - (t-ymin)/(ymax-ymin)*(bottom-top)
        d.line((left, y, right, y), fill="#E0E6EA", width=2)
        d.text((left-92, y-11), fmt_units(t), fill=COLORS["gray"], font=get_font(16))
    xs = np.linspace(left, right, len(actual_vals))
    colors = [COLORS["blue"], COLORS["gold"], COLORS["gray"], COLORS["red"]]
    series = [("Actual", actual_vals, COLORS["navy"], 5)]
    for i, (name, vals) in enumerate(predictions.items()):
        series.append((name, np.asarray(vals), colors[i % len(colors)], 3))
    for name, vals, color, width in series:
        pts = [(float(x), float(bottom - (v-ymin)/(ymax-ymin)*(bottom-top))) for x, v in zip(xs, vals)]
        d.line(pts, fill=color, width=width, joint="curve")
        if name == "Actual":
            for x, y in pts:
                d.ellipse((x-5, y-5, x+5, y+5), fill=color)
    for i, month in enumerate(actual["month"].tolist()):
        if i % 2 == 0:
            d.text((xs[i]-25, bottom+20), str(month)[5:7], fill=COLORS["gray"], font=get_font(16))
    lx, ly = left, 785
    for name, _, color, _ in series:
        d.line((lx, ly+10, lx+45, ly+10), fill=color, width=5)
        d.text((lx+55, ly), name, fill=COLORS["ink"], font=get_font(17))
        lx += 55 + d.textbbox((0,0), name, font=get_font(17))[2] + 70
    img.save(path)


def save_opportunity_matrix(kpi: pd.DataFrame, path: Path) -> None:
    w, h = 1600, 1000
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    draw_title(d, "2024 growth outlook versus 2023 share momentum", "Bubble size reflects 2023 unit sales; axes use portfolio-level share because most ATC markets are singletons in the sample")
    left, top, right, bottom = 180, 205, 1470, 825
    x = kpi["forecast_growth_2024"].to_numpy(float)
    y = kpi["portfolio_share_change_2023"].to_numpy(float)
    s = kpi["sales_2023"].to_numpy(float)
    x_ticks = nice_ticks(min(x.min(), -0.05), max(x.max(), 0.05), 7)
    y_ticks = nice_ticks(min(y.min(), -0.005), max(y.max(), 0.005), 7)
    xmin, xmax = min(x_ticks), max(x_ticks)
    ymin, ymax = min(y_ticks), max(y_ticks)
    def px(v: float) -> float: return left + (v-xmin)/(xmax-xmin)*(right-left)
    def py(v: float) -> float: return bottom - (v-ymin)/(ymax-ymin)*(bottom-top)
    for t in x_ticks:
        xx = px(t)
        d.line((xx, top, xx, bottom), fill="#EBEFF2", width=2)
        d.text((xx-25, bottom+15), f"{t:.0%}", fill=COLORS["gray"], font=get_font(15))
    for t in y_ticks:
        yy = py(t)
        d.line((left, yy, right, yy), fill="#EBEFF2", width=2)
        d.text((left-75, yy-10), f"{t*100:.2f}pp", fill=COLORS["gray"], font=get_font(15))
    d.line((px(0), top, px(0), bottom), fill=COLORS["navy"], width=3)
    d.line((left, py(0), right, py(0)), fill=COLORS["navy"], width=3)
    max_s = max(s.max(), 1)
    seg_colors = {
        "Growth Leader": COLORS["green"],
        "Emerging Opportunity": COLORS["teal"],
        "Defend": COLORS["gold"],
        "At Risk": COLORS["red"],
        "Market-led Growth": COLORS["blue"],
        "Monitor": COLORS["gray"],
    }
    label_inns=set(kpi.nlargest(9,"sales_2023")["INN"]) | set(kpi.nlargest(3,"forecast_growth_2024")["INN"]) | set(kpi.nsmallest(3,"forecast_growth_2024")["INN"])
    plotted=[]
    for _, row in kpi.sort_values("sales_2023").iterrows():
        xx, yy = px(float(row["forecast_growth_2024"])), py(float(row["portfolio_share_change_2023"]))
        radius = 10 + 30*math.sqrt(float(row["sales_2023"])/max_s)
        color = seg_colors.get(row["action_segment"], COLORS["gray"])
        d.ellipse((xx-radius, yy-radius, xx+radius, yy+radius), fill=color, outline="white", width=3)
        label = str(row["INN"]).replace("INUM", "IN").replace("UM", "")
        if row["INN"] in label_inns:
            plotted.append((xx,yy,radius,label))
    used=[]; font=get_font(13,True)
    for xx,yy,radius,label in sorted(plotted,key=lambda q:q[1]):
        box=d.textbbox((0,0),label,font=font); tw,th=box[2]-box[0],box[3]-box[1]
        base_x=xx+radius+5 if xx+radius+tw+5<right else xx-radius-tw-5
        candidates=[(base_x,yy-th/2+off) for off in [0,-20,20,-40,40,-60,60]]
        chosen=candidates[0]
        for tx,ty in candidates:
            ty=max(top,min(ty,bottom-th)); rect=(tx-4,ty-3,tx+tw+4,ty+th+3)
            if not any(not (rect[2]<r[0] or rect[0]>r[2] or rect[3]<r[1] or rect[1]>r[3]) for r in used):
                chosen=(tx,ty); used.append(rect); break
        d.text(chosen,label,fill=COLORS["ink"],font=font)
    d.text((left, 900), "Left: forecast decline    |    Right: forecast growth", fill=COLORS["gray"], font=get_font(17))
    d.text((1050, 900), "Up: gaining portfolio share", fill=COLORS["gray"], font=get_font(17))
    img.save(path)


def save_pca_chart(cluster_df: pd.DataFrame, path: Path) -> None:
    w, h = 1600, 900
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    draw_title(d, "Commercial archetypes separate scale, momentum and volatility", "PCA projection of standardized INN-level features; selected high-volume labels shown")
    left, top, right, bottom = 180, 190, 1470, 750
    x = cluster_df["pc1"].to_numpy(float)
    y = cluster_df["pc2"].to_numpy(float)
    xt = nice_ticks(x.min(), x.max(), 7); yt = nice_ticks(y.min(), y.max(), 7)
    xmin, xmax, ymin, ymax = min(xt), max(xt), min(yt), max(yt)
    px = lambda v: left+(v-xmin)/(xmax-xmin)*(right-left)
    py = lambda v: bottom-(v-ymin)/(ymax-ymin)*(bottom-top)
    for t in xt:
        d.line((px(t), top, px(t), bottom), fill="#E7ECEF", width=2)
    for t in yt:
        d.line((left, py(t), right, py(t)), fill="#E7ECEF", width=2)
    labels = cluster_df["cluster_label"].unique().tolist()
    palette = [COLORS["teal"], COLORS["blue"], COLORS["gold"], COLORS["red"], COLORS["gray"]]
    cmap = {lab: palette[i % len(palette)] for i, lab in enumerate(labels)}
    if "sales_2023" in cluster_df:
        label_inns=set(cluster_df.nlargest(11,"sales_2023")["INN"])
    else:
        label_inns=set(cluster_df["INN"])
    plotted=[]
    for _, row in cluster_df.iterrows():
        xx, yy = px(float(row["pc1"])), py(float(row["pc2"]))
        color = cmap[row["cluster_label"]]
        d.ellipse((xx-11, yy-11, xx+11, yy+11), fill=color, outline="white", width=2)
        if row["INN"] in label_inns:
            plotted.append((xx,yy,str(row["INN"]).replace("INUM", "IN").replace("UM", "")))
    used=[]; font=get_font(13)
    for xx,yy,label in sorted(plotted,key=lambda q:q[1]):
        box=d.textbbox((0,0),label,font=font); tw,th=box[2]-box[0],box[3]-box[1]
        base_x=xx+14 if xx+14+tw<right else xx-14-tw
        candidates=[(base_x,yy-th/2+off) for off in [0,-18,18,-36,36]]
        chosen=candidates[0]
        for tx,ty in candidates:
            ty=max(top,min(ty,bottom-th)); rect=(tx-4,ty-3,tx+tw+4,ty+th+3)
            if not any(not (rect[2]<r[0] or rect[0]>r[2] or rect[3]<r[1] or rect[1]>r[3]) for r in used):
                chosen=(tx,ty); used.append(rect); break
        d.text(chosen,label,fill=COLORS["ink"],font=font)
    d.text((left, bottom+25), "PC1", fill=COLORS["gray"], font=get_font(17, True))
    d.text((90, top), "PC2", fill=COLORS["gray"], font=get_font(17, True))
    lx, ly = left, 810
    for lab in labels:
        d.ellipse((lx, ly, lx+18, ly+18), fill=cmap[lab])
        d.text((lx+26, ly-2), lab, fill=COLORS["ink"], font=get_font(15))
        lx += 45 + d.textbbox((0,0), lab, font=get_font(15))[2]
    img.save(path)


def parse_description_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    strength_re = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|g|iu|u)\b", re.I)
    pack_hash_re = re.compile(r"#\s*(\d+)")
    pack_word_re = re.compile(r"\b(?:pack|blister|bottle|box)\s*(?:of\s*)?(\d+)\b", re.I)
    strengths, units, packs = [], [], []
    for text in out["Description"].fillna("").astype(str):
        m = strength_re.search(text)
        if m:
            strengths.append(float(m.group(1).replace(",", ".")))
            units.append(m.group(2).lower().replace("µg", "mcg").replace("ug", "mcg"))
        else:
            strengths.append(np.nan); units.append(None)
        found = pack_hash_re.findall(text)
        if found:
            packs.append(float(found[-1]))
        else:
            m2 = pack_word_re.search(text)
            packs.append(float(m2.group(1)) if m2 else np.nan)
    out["strength_value"] = strengths
    out["strength_unit"] = units
    out["pack_size"] = packs
    nfc = out["NFC (1)"].fillna("").str.lower()
    def form_cat(v: str) -> str:
        if "oral solid" in v: return "Oral solid"
        if "oral liquid" in v: return "Oral liquid"
        if "parenteral" in v: return "Parenteral"
        if "ophthalm" in v: return "Ophthalmic"
        if "topical" in v or "cutaneous" in v: return "Topical"
        if "rectal" in v or "vaginal" in v: return "Rectal/vaginal"
        if "respir" in v or "inhal" in v: return "Respiratory"
        return "Other"
    out["form_category"] = [form_cat(v) for v in nfc]
    return out


def seasonality_strength(y: np.ndarray) -> float:
    y = np.asarray(y, float)
    t = np.arange(len(y), dtype=float)
    if np.var(y) < 1e-12:
        return 0.0
    coef = np.polyfit(t, y, 1)
    detrended = y - np.polyval(coef, t)
    seasonal = np.array([np.mean(detrended[np.arange(len(y)) % 12 == m]) for m in range(12)])
    s = seasonal[np.arange(len(y)) % 12]
    resid = detrended - s
    den = np.var(s + resid)
    return float(np.clip(1 - np.var(resid)/den, 0, 1)) if den > 1e-12 else 0.0


def acf_lag(y: np.ndarray, lag: int) -> float:
    a, b = y[:-lag], y[lag:]
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def kmeans_numpy(X: np.ndarray, k: int, nstart: int = 50, max_iter: int = 200, seed: int = SEED) -> tuple[np.ndarray, np.ndarray, float]:
    rng = np.random.default_rng(seed + k)
    best = None
    for _ in range(nstart):
        centers = X[rng.choice(len(X), size=k, replace=False)].copy()
        labels = np.zeros(len(X), dtype=int)
        for _it in range(max_iter):
            dist = ((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            new_labels = dist.argmin(axis=1)
            new_centers = centers.copy()
            for j in range(k):
                if np.any(new_labels == j):
                    new_centers[j] = X[new_labels == j].mean(axis=0)
                else:
                    new_centers[j] = X[rng.integers(0, len(X))]
            if np.array_equal(new_labels, labels) and np.allclose(new_centers, centers):
                labels = new_labels; centers = new_centers; break
            labels, centers = new_labels, new_centers
        inertia = float(((X - centers[labels]) ** 2).sum())
        if best is None or inertia < best[2]:
            best = (labels.copy(), centers.copy(), inertia)
    assert best is not None
    return best


def silhouette_score_numpy(X: np.ndarray, labels: np.ndarray) -> float:
    n = len(X)
    dist = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(axis=2))
    scores = []
    for i in range(n):
        same = labels == labels[i]
        if same.sum() <= 1:
            scores.append(0.0); continue
        a = dist[i, same].sum() / (same.sum() - 1)
        b = min(dist[i, labels == lab].mean() for lab in np.unique(labels) if lab != labels[i])
        scores.append((b-a)/max(a, b, 1e-12))
    return float(np.mean(scores))


class LogisticL2:
    def __init__(self, lam: float = 1.0, max_iter: int = 100):
        self.lam = lam; self.max_iter = max_iter; self.coef_ = None
    def fit(self, X: np.ndarray, y: np.ndarray):
        Xb = np.column_stack([np.ones(len(X)), X])
        b = np.zeros(Xb.shape[1])
        for _ in range(self.max_iter):
            z = np.clip(Xb @ b, -30, 30)
            p = 1/(1+np.exp(-z))
            grad = Xb.T @ (p-y)
            reg = self.lam * b; reg[0] = 0
            grad += reg
            w = np.clip(p*(1-p), 1e-5, None)
            H = Xb.T @ (Xb*w[:, None])
            H += np.diag(np.r_[0.0, np.repeat(self.lam, X.shape[1])]) + np.eye(Xb.shape[1])*1e-8
            step = np.linalg.solve(H, grad)
            b -= step
            if np.max(np.abs(step)) < 1e-7: break
        self.coef_ = b
        return self
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        z = np.clip(np.column_stack([np.ones(len(X)), X]) @ self.coef_, -30, 30)
        return 1/(1+np.exp(-z))


class ElasticNetLogistic:
    def __init__(self, lam: float = 0.1, alpha: float = 0.5, max_iter: int = 2500):
        self.lam = lam; self.alpha = alpha; self.max_iter = max_iter; self.coef_ = None
    def fit(self, X: np.ndarray, y: np.ndarray):
        Xb = np.column_stack([np.ones(len(X)), X])
        b = np.zeros(Xb.shape[1])
        spectral = np.linalg.norm(Xb, 2) ** 2 / len(Xb)
        step = 1 / (0.25*spectral + self.lam*(1-self.alpha) + 1e-8)
        for _ in range(self.max_iter):
            old = b.copy()
            p = 1/(1+np.exp(-np.clip(Xb@b, -30, 30)))
            grad = Xb.T@(p-y)/len(y)
            grad[1:] += self.lam*(1-self.alpha)*b[1:]
            b -= step*grad
            thresh = step*self.lam*self.alpha
            b[1:] = np.sign(b[1:]) * np.maximum(np.abs(b[1:])-thresh, 0)
            if np.max(np.abs(b-old)) < 1e-7: break
        self.coef_ = b
        return self
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        z = np.clip(np.column_stack([np.ones(len(X)), X]) @ self.coef_, -30, 30)
        return 1/(1+np.exp(-z))


@dataclass
class TreeNode:
    value: float
    feature: int | None = None
    threshold: float | None = None
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None


class SimpleTree:
    def __init__(self, max_depth: int = 3, min_leaf: int = 10, criterion: str = "mse", max_features: int | None = None, seed: int = SEED):
        self.max_depth=max_depth; self.min_leaf=min_leaf; self.criterion=criterion; self.max_features=max_features
        self.rng=np.random.default_rng(seed); self.root=None; self.importance_=None
    def _impurity(self, y: np.ndarray) -> float:
        if len(y)==0: return 0.0
        if self.criterion == "gini":
            p=y.mean(); return len(y)*(p*(1-p))
        return float(((y-y.mean())**2).sum())
    def _build(self, X: np.ndarray, y: np.ndarray, depth: int) -> TreeNode:
        node=TreeNode(float(y.mean()) if len(y) else 0.0)
        if depth>=self.max_depth or len(y)<2*self.min_leaf or np.var(y)<1e-10:
            return node
        p=X.shape[1]
        feats=np.arange(p)
        if self.max_features is not None and self.max_features < p:
            feats=self.rng.choice(feats, self.max_features, replace=False)
        parent=self._impurity(y); best_gain=0.0; best=None
        for j in feats:
            col=X[:,j]
            qs=np.unique(np.quantile(col, [0.1,0.2,0.35,0.5,0.65,0.8,0.9]))
            for thr in qs:
                mask=col<=thr
                if mask.sum()<self.min_leaf or (~mask).sum()<self.min_leaf: continue
                gain=parent-self._impurity(y[mask])-self._impurity(y[~mask])
                if gain>best_gain+1e-12:
                    best_gain=gain; best=(j,float(thr),mask)
        if best is None: return node
        j,thr,mask=best
        node.feature=j; node.threshold=thr
        self.importance_[j]+=best_gain
        node.left=self._build(X[mask],y[mask],depth+1)
        node.right=self._build(X[~mask],y[~mask],depth+1)
        return node
    def fit(self,X:np.ndarray,y:np.ndarray):
        self.importance_=np.zeros(X.shape[1])
        self.root=self._build(X,y,0)
        return self
    def _predict_one(self,row:np.ndarray,node:TreeNode)->float:
        while node.feature is not None:
            node=node.left if row[node.feature]<=node.threshold else node.right
        return node.value
    def predict(self,X:np.ndarray)->np.ndarray:
        return np.array([self._predict_one(row,self.root) for row in X])


class RandomForestSimple:
    def __init__(self,n_trees:int=100,max_depth:int=3,min_leaf:int=10,seed:int=SEED):
        self.n_trees=n_trees; self.max_depth=max_depth; self.min_leaf=min_leaf; self.seed=seed; self.trees=[]; self.importance_=None
    def fit(self,X:np.ndarray,y:np.ndarray):
        rng=np.random.default_rng(self.seed); self.trees=[]; self.importance_=np.zeros(X.shape[1])
        for i in range(self.n_trees):
            idx=rng.integers(0,len(X),len(X))
            tree=SimpleTree(self.max_depth,self.min_leaf,"gini",max(1,int(math.sqrt(X.shape[1]))),self.seed+i)
            tree.fit(X[idx],y[idx]); self.trees.append(tree); self.importance_+=tree.importance_
        if self.importance_.sum()>0:self.importance_/=self.importance_.sum()
        return self
    def predict_proba(self,X:np.ndarray)->np.ndarray:
        return np.mean([t.predict(X) for t in self.trees],axis=0)


class GradientBoostingSimple:
    def __init__(self,n_trees:int=100,max_depth:int=2,min_leaf:int=12,learning_rate:float=0.05,task:str="classification",seed:int=SEED):
        self.n_trees=n_trees; self.max_depth=max_depth; self.min_leaf=min_leaf; self.learning_rate=learning_rate; self.task=task; self.seed=seed
        self.trees=[]; self.initial_=0.0; self.importance_=None
    def fit(self,X:np.ndarray,y:np.ndarray):
        self.trees=[]; self.importance_=np.zeros(X.shape[1])
        if self.task=="classification":
            p=np.clip(y.mean(),1e-4,1-1e-4); self.initial_=float(np.log(p/(1-p)))
        else:self.initial_=float(y.mean())
        f=np.repeat(self.initial_,len(y))
        for i in range(self.n_trees):
            if self.task=="classification":
                pred=1/(1+np.exp(-np.clip(f,-30,30))); resid=y-pred
            else:resid=y-f
            tree=SimpleTree(self.max_depth,self.min_leaf,"mse",None,self.seed+i).fit(X,resid)
            update=tree.predict(X); f+=self.learning_rate*update
            self.trees.append(tree); self.importance_+=tree.importance_
        if self.importance_.sum()>0:self.importance_/=self.importance_.sum()
        return self
    def predict_raw(self,X:np.ndarray)->np.ndarray:
        f=np.repeat(self.initial_,len(X)).astype(float)
        for tree in self.trees:f+=self.learning_rate*tree.predict(X)
        return f
    def predict_proba(self,X:np.ndarray)->np.ndarray:
        f=self.predict_raw(X); return 1/(1+np.exp(-np.clip(f,-30,30)))
    def predict(self,X:np.ndarray)->np.ndarray:return self.predict_raw(X)


class RidgeModel:
    def __init__(self,lam:float=1.0):self.lam=lam; self.mean_=None; self.std_=None; self.coef_=None
    def fit(self,X:np.ndarray,y:np.ndarray):
        self.mean_=X.mean(axis=0); self.std_=X.std(axis=0); self.std_[self.std_<1e-8]=1
        Z=(X-self.mean_)/self.std_; Xb=np.column_stack([np.ones(len(Z)),Z])
        P=np.eye(Xb.shape[1])*self.lam; P[0,0]=0
        self.coef_=np.linalg.solve(Xb.T@Xb+P,Xb.T@y)
        return self
    def predict(self,X:np.ndarray)->np.ndarray:
        Z=(X-self.mean_)/self.std_; return np.column_stack([np.ones(len(Z)),Z])@self.coef_


def roc_auc(y:np.ndarray,s:np.ndarray)->float:
    y=np.asarray(y,int); s=np.asarray(s,float); pos=y.sum(); neg=len(y)-pos
    if pos==0 or neg==0:return float("nan")
    order=np.argsort(s); ranks=np.empty(len(s),float)
    i=0
    while i<len(s):
        j=i
        while j+1<len(s) and s[order[j+1]]==s[order[i]]:j+=1
        ranks[order[i:j+1]]=(i+j+2)/2
        i=j+1
    return float((ranks[y==1].sum()-pos*(pos+1)/2)/(pos*neg))


def average_precision(y:np.ndarray,s:np.ndarray)->float:
    order=np.argsort(-s); yy=y[order]; total=yy.sum()
    if total==0:return float("nan")
    cum=np.cumsum(yy); prec=cum/(np.arange(len(yy))+1)
    return float((prec*yy).sum()/total)


def classification_metrics(y:np.ndarray,s:np.ndarray)->dict[str,float]:
    pred=(s>=0.5).astype(int); tp=((pred==1)&(y==1)).sum(); fp=((pred==1)&(y==0)).sum(); fn=((pred==0)&(y==1)).sum()
    n_top=max(1,int(math.ceil(len(y)*0.2))); top=np.argsort(-s)[:n_top]
    p20=float(y[top].mean()); base=float(y.mean())
    return {"roc_auc":roc_auc(y,s),"pr_auc":average_precision(y,s),"precision":float(tp/max(tp+fp,1)),"recall":float(tp/max(tp+fn,1)),"precision_top20":p20,"lift_top20":p20/base if base else np.nan,"winner_rate":base}


def fit_classification_models(Xtr:np.ndarray,ytr:np.ndarray,Xv:np.ndarray,yv:np.ndarray,Xt:np.ndarray,yt:np.ndarray,feature_names:list[str]):
    med=np.nanmedian(Xtr,axis=0); Xtr0=np.where(np.isnan(Xtr),med,Xtr); Xv0=np.where(np.isnan(Xv),med,Xv); Xt0=np.where(np.isnan(Xt),med,Xt)
    mean=Xtr0.mean(axis=0); std=Xtr0.std(axis=0); std[std<1e-8]=1
    Ztr=(Xtr0-mean)/std; Zv=(Xv0-mean)/std; Zt=(Xt0-mean)/std
    candidates=[]
    for lam in [0.01,0.1,1.0,10.0]:
        m=LogisticL2(lam).fit(Ztr,ytr); candidates.append(("Logistic L2",{"lambda":lam},m,m.predict_proba(Zv),"scaled"))
    for lam in [0.01,0.05,0.1,0.3]:
        for alpha in [0.25,0.5,0.75]:
            m=ElasticNetLogistic(lam,alpha).fit(Ztr,ytr); candidates.append(("Elastic Net",{"lambda":lam,"alpha":alpha},m,m.predict_proba(Zv),"scaled"))
    for depth in [2,3]:
        for leaf in [10,20]:
            m=RandomForestSimple(100,depth,leaf).fit(Xtr0,ytr); candidates.append(("Random Forest",{"trees":100,"depth":depth,"min_leaf":leaf},m,m.predict_proba(Xv0),"raw"))
    for depth in [1,2]:
        for lr in [0.05,0.1]:
            m=GradientBoostingSimple(100,depth,12,lr,"classification").fit(Xtr0,ytr); candidates.append(("Boosted Trees",{"trees":100,"depth":depth,"learning_rate":lr},m,m.predict_proba(Xv0),"raw"))
    best_by_name={}
    for name,params,model,sv,kind in candidates:
        met=classification_metrics(yv,sv)
        score=(met["precision_top20"],met["pr_auc"],met["roc_auc"])
        if name not in best_by_name or score>best_by_name[name][0]:best_by_name[name]=(score,params,model,kind,met)
    rows=[]; fitted={}
    for name,(score,params,model,kind,vmet) in best_by_name.items():
        st=model.predict_proba(Zt if kind=="scaled" else Xt0)
        tmet=classification_metrics(yt,st)
        row={"model":name,"parameters":json.dumps(params),**{f"validation_{k}":v for k,v in vmet.items()},**{f"test_{k}":v for k,v in tmet.items()}}
        rows.append(row); fitted[name]=(model,kind,st)
    selected=max(rows,key=lambda r:(r["validation_precision_top20"],r["validation_pr_auc"],r["validation_roc_auc"]))["model"]
    model,kind,base_scores=fitted[selected]
    Xbase=Zt if kind=="scaled" else Xt0
    base_ap=average_precision(yt,base_scores); perm=[]; rng=np.random.default_rng(SEED+88)
    for j,name in enumerate(feature_names):
        drops=[]
        for _ in range(15):
            xp=Xbase.copy(); xp[:,j]=rng.permutation(xp[:,j])
            drops.append(base_ap-average_precision(yt,model.predict_proba(xp)))
        perm.append({"feature":name,"pr_auc_drop":float(np.mean(drops))})
    perm=sorted(perm,key=lambda r:r["pr_auc_drop"],reverse=True)
    return rows, selected, perm, {"median":med,"mean":mean,"std":std}


def forecast_metrics(actual:np.ndarray,pred:np.ndarray,train:np.ndarray)->dict[str,float]:
    err=pred-actual; denom=max(float(actual.sum()),1e-12)
    seasonal=np.abs(train[12:]-train[:-12]); scale=max(float(seasonal.mean()),1e-12)
    return {"WAPE":float(np.abs(err).sum()/denom),"MAE":float(np.abs(err).mean()),"RMSE":float(np.sqrt(np.mean(err**2))),"MASE":float(np.abs(err).mean()/scale),"Bias":float(err.sum()/denom)}


def holt_winters_forecast(series:np.ndarray,h:int,alpha:float,beta:float,gamma:float,phi:float=0.9)->np.ndarray:
    y=np.asarray(series,float); m=12
    if len(y)<2*m:return np.repeat(max(y[-1],0),h)
    level=float(np.mean(y[:m])); trend=float((np.mean(y[m:2*m])-np.mean(y[:m]))/m)
    season=(y[:m]-level).astype(float)
    for t,val in enumerate(y):
        idx=t%m; old=level
        level=alpha*(val-season[idx])+(1-alpha)*(level+phi*trend)
        trend=beta*(level-old)+(1-beta)*phi*trend
        season[idx]=gamma*(val-level)+(1-gamma)*season[idx]
    out=[]
    for step in range(1,h+1):
        damp=sum(phi**j for j in range(1,step+1))
        out.append(max(level+damp*trend+season[(len(y)+step-1)%m],0.0))
    return np.array(out)


def forecast_feature(history:np.ndarray,inn_idx:int,target_t:int,static:np.ndarray)->np.ndarray:
    y=history[:,inn_idx]; port=history.sum(axis=1)
    lag=lambda k:y[-k]
    vals=[np.log1p(lag(k)) for k in [1,2,3,6,12]]
    vals += [np.log1p(np.mean(y[-k:])) for k in [3,6,12]]
    vals += [float(np.std(np.log1p(y[-k:]))) for k in [3,6]]
    vals += [np.log1p(y[-1])-np.log1p(y[-2]),np.log1p(y[-1])-np.log1p(y[-12])]
    month=(target_t%12)+1
    vals += [math.sin(2*math.pi*month/12),math.cos(2*math.pi*month/12)]
    vals += [np.log1p(port[-1]),np.log1p(port[-12]),np.log1p(port[-1])-np.log1p(port[-12])]
    vals += static[inn_idx].tolist()
    one=np.zeros(history.shape[1]); one[inn_idx]=1
    return np.r_[vals,one]


def make_forecast_training(Y:np.ndarray,end:int,static:np.ndarray)->tuple[np.ndarray,np.ndarray]:
    X=[]; target=[]
    for t in range(12,end):
        hist=Y[:t]
        for i in range(Y.shape[1]):
            X.append(forecast_feature(hist,i,t,static)); target.append(np.log1p(Y[t,i]))
    return np.asarray(X,float),np.asarray(target,float)


def recursive_global_forecast(model:Any,history:np.ndarray,h:int,static:np.ndarray,log_cap:float)->np.ndarray:
    hist=history.copy(); outs=[]
    for step in range(h):
        t=len(hist); X=np.array([forecast_feature(hist,i,t,static) for i in range(hist.shape[1])])
        lp=model.predict(X); lp=np.clip(lp,0,log_cap)
        pred=np.expm1(lp); outs.append(pred); hist=np.vstack([hist,pred])
    return np.vstack(outs)


def build_forecast_models(Y:np.ndarray,static:np.ndarray):
    names=[]
    val_preds={}; test_preds={}; prod_builders={}
    val_actual=Y[36:48]; test_actual=Y[48:60]
    val_preds["Seasonal Naive"]=Y[24:36].copy(); test_preds["Seasonal Naive"]=Y[36:48].copy()
    prod_builders["Seasonal Naive"]=lambda full: full[-12:].copy()
    best_hw=None
    for a in [0.2,0.5,0.8]:
        for b in [0.05,0.2,0.5]:
            for g in [0.05,0.2,0.5]:
                p=np.column_stack([holt_winters_forecast(Y[:36,i],12,a,b,g,0.9) for i in range(Y.shape[1])])
                met=forecast_metrics(val_actual,p,Y[:36])
                if best_hw is None or met["WAPE"]<best_hw[0]:best_hw=(met["WAPE"],a,b,g,p)
    _,a,b,g,pv=best_hw
    val_preds["Damped ETS"]=pv
    test_preds["Damped ETS"]=np.column_stack([holt_winters_forecast(Y[:48,i],12,a,b,g,0.9) for i in range(Y.shape[1])])
    prod_builders["Damped ETS"]=lambda full,a=a,b=b,g=g: np.column_stack([holt_winters_forecast(full[:,i],12,a,b,g,0.9) for i in range(full.shape[1])])
    Xtr,ytr=make_forecast_training(Y,36,static); log_cap=float(np.quantile(ytr,0.999)+math.log(2))
    best_r=None
    for lam in [0.1,1,10,100,1000]:
        m=RidgeModel(lam).fit(Xtr,ytr); p=recursive_global_forecast(m,Y[:36],12,static,log_cap)
        met=forecast_metrics(val_actual,p,Y[:36])
        if best_r is None or met["WAPE"]<best_r[0]:best_r=(met["WAPE"],lam,p)
    _,lam,pv=best_r; val_preds["Global Ridge ARX"]=pv
    X48,y48=make_forecast_training(Y,48,static); mr=RidgeModel(lam).fit(X48,y48); cap48=float(np.quantile(y48,0.999)+math.log(2))
    test_preds["Global Ridge ARX"]=recursive_global_forecast(mr,Y[:48],12,static,cap48)
    def ridge_prod(full,lam=lam):
        X,y=make_forecast_training(full,len(full),static); m=RidgeModel(lam).fit(X,y); cap=float(np.quantile(y,0.999)+math.log(2)); return recursive_global_forecast(m,full,12,static,cap)
    prod_builders["Global Ridge ARX"]=ridge_prod
    best_b=None
    for depth in [1,2]:
        for lr in [0.05,0.1]:
            for nt in [75,125]:
                m=GradientBoostingSimple(nt,depth,15,lr,"regression",SEED+44).fit(Xtr,ytr)
                p=recursive_global_forecast(m,Y[:36],12,static,log_cap)
                met=forecast_metrics(val_actual,p,Y[:36])
                if best_b is None or met["WAPE"]<best_b[0]:best_b=(met["WAPE"],depth,lr,nt,p)
    _,depth,lr,nt,pv=best_b; val_preds["Global Boosted Trees"]=pv
    mb=GradientBoostingSimple(nt,depth,15,lr,"regression",SEED+44).fit(X48,y48)
    test_preds["Global Boosted Trees"]=recursive_global_forecast(mb,Y[:48],12,static,cap48)
    def boost_prod(full,depth=depth,lr=lr,nt=nt):
        X,y=make_forecast_training(full,len(full),static); m=GradientBoostingSimple(nt,depth,15,lr,"regression",SEED+44).fit(X,y); cap=float(np.quantile(y,0.999)+math.log(2)); return recursive_global_forecast(m,full,12,static,cap)
    prod_builders["Global Boosted Trees"]=boost_prod
    indiv=list(val_preds)
    inv=np.array([1/max(forecast_metrics(val_actual,val_preds[n],Y[:36])["WAPE"],1e-6) for n in indiv]); weights=inv/inv.sum()
    val_preds["Validation-weighted Ensemble"]=sum(weights[i]*val_preds[n] for i,n in enumerate(indiv))
    test_preds["Validation-weighted Ensemble"]=sum(weights[i]*test_preds[n] for i,n in enumerate(indiv))
    prod_builders["Validation-weighted Ensemble"]=lambda full: sum(weights[i]*prod_builders[n](full) for i,n in enumerate(indiv))
    rows=[]
    for name in val_preds:
        vm=forecast_metrics(val_actual,val_preds[name],Y[:36]); tm=forecast_metrics(test_actual,test_preds[name],Y[:48])
        rows.append({"model":name,**{f"validation_{k}":v for k,v in vm.items()},**{f"test_{k}":v for k,v in tm.items()}})
    selected=min(rows,key=lambda r:r["validation_WAPE"])["model"]
    prod=prod_builders[selected](Y)
    log_res=np.log1p(val_actual)-np.log1p(np.maximum(val_preds[selected],0))
    lower=np.zeros_like(prod); upper=np.zeros_like(prod)
    for h in range(12):
        q10,q90=np.quantile(log_res[h],[0.1,0.9])
        lower[h]=np.maximum(np.expm1(np.log1p(prod[h])+q10),0)
        upper[h]=np.maximum(np.expm1(np.log1p(prod[h])+q90),0)
    return rows,selected,val_preds,test_preds,prod,lower,upper,weights,indiv


def assign_cluster_labels(kpi:pd.DataFrame,labels:np.ndarray)->dict[int,str]:
    temp=kpi.copy(); temp["cluster"]=labels
    summary=temp.groupby("cluster").agg(scale=("sales_2023","mean"),share=("portfolio_share_2023","mean"),growth=("yoy_growth_2023","mean"),momentum=("portfolio_share_change_2023","mean"),volatility=("cv_monthly","mean"))
    summary["scale_score"]=np.log1p(summary["scale"])+3*summary["share"]
    summary["growth_score"]=summary["growth"].fillna(0)+8*summary["momentum"].fillna(0)-0.15*summary["volatility"]
    remaining=set(summary.index.tolist()); mapping={}
    risk=int(summary["growth_score"].idxmin()); mapping[risk]="At-Risk / Declining"; remaining.remove(risk)
    mature=max(remaining,key=lambda c:summary.loc[c,"scale_score"]); mapping[mature]="Mature Leaders"; remaining.remove(mature)
    if remaining:
        growth=max(remaining,key=lambda c:summary.loc[c,"growth_score"]); mapping[growth]="Growth / Emerging"; remaining.remove(growth)
    for c in remaining:mapping[int(c)]="Niche / Volatile"
    return mapping


def main(input_path:Path,output_dir:Path)->None:
    ensure_dir(output_dir); fig_dir=output_dir/"figures"; ensure_dir(fig_dir)
    raw=pd.read_csv(input_path)
    raw=parse_description_features(raw)
    month_cols=[c for c in raw.columns if re.fullmatch(r"20\d{2} \d{2}",str(c))]
    months=pd.to_datetime([c.replace(" ","-")+"-01" for c in month_cols])
    sales_matrix=raw[month_cols].to_numpy(float)
    static_cols=["Morion ID","ATC Code (1)","ATC Code (2)","ATC Code (3)","ATC Code (4)","ATC Code (5)","Brand","INN","NFC (1)","Description","strength_value","strength_unit","pack_size","form_category"]
    long=raw[static_cols+month_cols].melt(id_vars=static_cols,value_vars=month_cols,var_name="month",value_name="sales")
    long["month"]=pd.to_datetime(long["month"].str.replace(" ","-")+"-01")
    long["year"]=long["month"].dt.year
    inn_month=long.groupby(["INN","month"],as_index=False)["sales"].sum()
    inn_names=sorted(raw["INN"].unique())
    pivot=inn_month.pivot(index="month",columns="INN",values="sales").reindex(index=months,columns=inn_names).fillna(0)
    Y=pivot.to_numpy(float)
    annual=inn_month.assign(year=inn_month["month"].dt.year).groupby(["INN","year"],as_index=False)["sales"].sum()
    portfolio_annual=annual.groupby("year",as_index=False)["sales"].sum()
    ann_piv=annual.pivot(index="INN",columns="year",values="sales").reindex(inn_names).fillna(0)
    port_yoy=portfolio_annual.set_index("year").loc[2023,"sales"]/portfolio_annual.set_index("year").loc[2022,"sales"]-1
    counts=raw.groupby("INN").agg(sku_count=("Morion ID","nunique"),brand_count=("Brand","nunique"),strength_count=("strength_value","nunique"),pack_count=("pack_size","nunique"),dosage_form_count=("form_category","nunique"),atc3_count=("ATC Code (3)","nunique"),atc4_count=("ATC Code (4)","nunique")).reindex(inn_names)
    kpi_rows=[]
    for i,inn in enumerate(inn_names):
        y=Y[:,i]; s19=float(ann_piv.loc[inn,2019]); s22=float(ann_piv.loc[inn,2022]); s23=float(ann_piv.loc[inn,2023])
        yoy=s23/s22-1 if s22>0 else np.nan; cagr=(s23/s19)**0.25-1 if s19>0 and s23>=0 else np.nan
        sh22=s22/float(ann_piv[2022].sum()); sh23=s23/float(ann_piv[2023].sum())
        slope=np.polyfit(np.arange(60),y,1)[0]/max(y.mean(),1e-12)
        row={"INN":inn,"sales_2019":s19,"sales_2022":s22,"sales_2023":s23,"portfolio_share_2022":sh22,"portfolio_share_2023":sh23,"portfolio_share_change_2023":sh23-sh22,"yoy_growth_2023":yoy,"cagr_2019_2023":cagr,"relative_growth_2023":yoy-port_yoy if np.isfinite(yoy) else np.nan,"cv_monthly":float(y.std()/max(y.mean(),1e-12)),"trend_slope_normalized":float(slope),"seasonality_strength":seasonality_strength(y),"zero_month_ratio":float((y==0).mean()),"lag12_acf":acf_lag(y,12),**counts.loc[inn].to_dict()}
        kpi_rows.append(row)
    kpi=pd.DataFrame(kpi_rows)
    # Market peers: prefer ATC4 where >=2 sampled INNs; otherwise ATC3 where >=2.
    atc4_peer=raw.groupby("ATC Code (4)")["INN"].nunique(); atc3_peer=raw.groupby("ATC Code (3)")["INN"].nunique()
    raw["market_level"]=np.where(raw["ATC Code (4)"].map(atc4_peer)>=2,"ATC4",np.where(raw["ATC Code (3)"].map(atc3_peer)>=2,"ATC3","No sampled peer"))
    raw["market_name"]=np.where(raw["market_level"]=="ATC4",raw["ATC Code (4)"],np.where(raw["market_level"]=="ATC3",raw["ATC Code (3)"],"No sampled peer"))
    peer_long=raw[static_cols+["market_level","market_name"]+month_cols].melt(id_vars=static_cols+["market_level","market_name"],value_vars=month_cols,var_name="month",value_name="sales")
    peer_long["year"]=peer_long["month"].str[:4].astype(int)
    peer=peer_long[peer_long["market_level"]!="No sampled peer"].groupby(["market_level","market_name","INN","year"],as_index=False)["sales"].sum()
    peer_p=peer.pivot(index=["market_level","market_name","INN"],columns="year",values="sales").fillna(0).reset_index()
    peer_rows=[]
    for (level,market),g in peer_p.groupby(["market_level","market_name"]):
        m22=float(g[2022].sum()); m23=float(g[2023].sum()); n=int(len(g)); hhi=0.0
        for _,r in g.iterrows():
            p22=float(r[2022]); p23=float(r[2023]); sh22=p22/m22 if m22 else np.nan; sh23=p23/m23 if m23 else np.nan
            expected=m23*sh22 if np.isfinite(sh22) else np.nan
            hhi+=(sh23 if np.isfinite(sh23) else 0)**2
            peer_rows.append({"market_level":level,"market_name":market,"peer_INN_count":n,"INN":r["INN"],"sales_2022":p22,"sales_2023":p23,"market_sales_2022":m22,"market_sales_2023":m23,"market_growth_2023":m23/m22-1 if m22 else np.nan,"share_2022":sh22,"share_2023":sh23,"share_change_pp":sh23-sh22,"product_growth_2023":p23/p22-1 if p22 else np.nan,"relative_growth_2023":(p23/p22-1)-(m23/m22-1) if p22 and m22 else np.nan,"market_expansion_effect":expected-p22 if np.isfinite(expected) else np.nan,"share_effect":p23-expected if np.isfinite(expected) else np.nan,"total_growth":p23-p22})
        for rr in peer_rows[-n:]:rr["HHI_2023"]=hhi
    peer_df=pd.DataFrame(peer_rows)
    # Outlier flags are retained, not deleted.
    spike_count=0; stockout_count=0
    for y in sales_matrix:
        for t in range(1,len(y)-1):
            if y[t]==0 and y[t-1]>0 and y[t+1]>0:stockout_count+=1
            local=np.r_[y[max(0,t-3):t],y[t+1:min(len(y),t+4)]]
            pos=local[local>0]
            if len(pos)>=2:
                med=float(np.median(pos))
                if y[t]>max(5*med,med+50):spike_count+=1
    # Classification dataset.
    portfolio=Y.sum(axis=1); shares=Y/portfolio[:,None]; hhi=(shares**2).sum(axis=1)
    class_features=["log_sales","lag1","lag3","lag6","lag12","roll_mean3","roll_mean6","roll_mean12","roll_sd3","roll_sd6","current_share","share_change3","share_change6","share_change12","growth3","growth6","growth12","market_growth12","relative_growth12","HHI","log_sku_count","log_strength_count","log_pack_count","log_form_count","seasonality_strength","month_sin","month_cos"]
    cls_rows=[]; X=[]; dates=[]; inns=[]; fchanges=[]
    for t in range(12,54):
        changes=shares[t+6]-shares[t]; winner_idx=set(np.argsort(-changes)[:max(1,int(math.ceil(len(inn_names)*0.25)))])
        for i,inn in enumerate(inn_names):
            y=Y[:,i]; lg=lambda k:np.log1p(y[t-k]); prod12=lg(0)-lg(12); mg12=np.log1p(portfolio[t])-np.log1p(portfolio[t-12])
            vals=[np.log1p(y[t]),lg(1),lg(3),lg(6),lg(12),np.log1p(y[t-2:t+1].mean()),np.log1p(y[t-5:t+1].mean()),np.log1p(y[t-11:t+1].mean()),np.std(np.log1p(y[t-2:t+1])),np.std(np.log1p(y[t-5:t+1])),shares[t,i],shares[t,i]-shares[t-3,i],shares[t,i]-shares[t-6,i],shares[t,i]-shares[t-12,i],lg(0)-lg(3),lg(0)-lg(6),prod12,mg12,prod12-mg12,hhi[t],np.log1p(kpi.loc[kpi.INN==inn,"sku_count"].iloc[0]),np.log1p(kpi.loc[kpi.INN==inn,"strength_count"].iloc[0]),np.log1p(kpi.loc[kpi.INN==inn,"pack_count"].iloc[0]),np.log1p(kpi.loc[kpi.INN==inn,"dosage_form_count"].iloc[0]),kpi.loc[kpi.INN==inn,"seasonality_strength"].iloc[0],math.sin(2*math.pi*(t%12+1)/12),math.cos(2*math.pi*(t%12+1)/12)]
            X.append(vals); dates.append(months[t]); inns.append(inn); fchanges.append(changes[i]); cls_rows.append(1 if i in winner_idx else 0)
    X=np.asarray(X,float); yy=np.asarray(cls_rows,int); dates=np.asarray(dates,dtype="datetime64[ns]"); inns=np.asarray(inns); fchanges=np.asarray(fchanges)
    train=dates<=np.datetime64("2021-12-01"); val=(dates>=np.datetime64("2022-01-01"))&(dates<=np.datetime64("2022-06-01")); test=(dates>=np.datetime64("2022-07-01"))
    class_results,selected_cls,importance,_=fit_classification_models(X[train],yy[train],X[val],yy[val],X[test],yy[test],class_features)
    # Forecasting.
    static=np.column_stack([np.log1p(kpi.set_index("INN").loc[inn_names,c].to_numpy(float)) for c in ["sku_count","strength_count","pack_count","dosage_form_count"]]+[kpi.set_index("INN").loc[inn_names,"seasonality_strength"].to_numpy(float)])
    forecast_rows,selected_forecast,val_preds,test_preds,prod,lower,upper,weights,ensemble_members=build_forecast_models(Y,static)
    actual_2023=Y[48:60]
    forecast_total_2024=prod.sum(axis=0); lower_total=lower.sum(axis=0); upper_total=upper.sum(axis=0)
    kpi["forecast_2024"]=forecast_total_2024
    kpi["forecast_growth_2024"]=kpi["forecast_2024"]/kpi["sales_2023"]-1
    kpi["forecast_2024_lower80"]=lower_total; kpi["forecast_2024_upper80"]=upper_total
    share_median=float(kpi["portfolio_share_2023"].median())
    def action(r):
        gain=r["portfolio_share_change_2023"]>0; fg=r["forecast_growth_2024"]>0; high=r["portfolio_share_2023"]>=share_median
        if fg and gain and high:return "Growth Leader"
        if fg and gain and not high:return "Emerging Opportunity"
        if high and not gain:return "Defend"
        if (not fg) and (not gain):return "At Risk"
        if fg:return "Market-led Growth"
        return "Monitor"
    kpi["action_segment"]=kpi.apply(action,axis=1)
    # Clustering after forecast is available.
    cluster_features=["sales_2023","portfolio_share_2023","portfolio_share_change_2023","cagr_2019_2023","yoy_growth_2023","relative_growth_2023","cv_monthly","trend_slope_normalized","seasonality_strength","lag12_acf","sku_count","strength_count","pack_count","dosage_form_count"]
    C=kpi[cluster_features].copy()
    for c in ["sales_2023","sku_count","strength_count","pack_count","dosage_form_count"]:C[c]=np.log1p(C[c])
    C=C.fillna(C.median()); Cz=(C-C.mean())/C.std(ddof=0).replace(0,1); scores=[]; km={}
    for kk in [3,4,5]:
        lab,cent,inertia=kmeans_numpy(Cz.to_numpy(),kk); sil=silhouette_score_numpy(Cz.to_numpy(),lab); scores.append({"k":kk,"silhouette":sil,"WSS":inertia}); km[kk]=(lab,cent)
    best_k=max(scores,key=lambda r:r["silhouette"])["k"]; labels,centers=km[best_k]
    mapping=assign_cluster_labels(kpi,labels); kpi["cluster_id"]=labels+1; kpi["cluster_label"]=[mapping[int(v)] for v in labels]
    U,S,Vt=np.linalg.svd(Cz.to_numpy(),full_matrices=False); pcs=U[:,:2]*S[:2]
    kpi["pc1"]=pcs[:,0]; kpi["pc2"]=pcs[:,1]
    cluster_summary=kpi.groupby(["cluster_id","cluster_label"],as_index=False).agg(INN_count=("INN","count"),sales_2023=("sales_2023","sum"),avg_yoy_growth=("yoy_growth_2023","mean"),avg_share_change=("portfolio_share_change_2023","mean"),avg_forecast_growth=("forecast_growth_2024","mean"),avg_cv=("cv_monthly","mean"))
    # Monthly and annual forecast exports.
    forecast_monthly=[]
    for h in range(12):
        month=(pd.Timestamp("2024-01-01")+pd.DateOffset(months=h)).strftime("%Y-%m")
        for i,inn in enumerate(inn_names):forecast_monthly.append({"month":month,"INN":inn,"forecast":prod[h,i],"lower80":lower[h,i],"upper80":upper[h,i],"selected_model":selected_forecast})
    monthly_export=inn_month.copy(); monthly_export["month"]=monthly_export["month"].dt.strftime("%Y-%m")
    sku_export=raw[static_cols+["market_level","market_name"]].copy()
    for year in range(2019,2024):sku_export[f"sales_{year}"]=raw[[c for c in month_cols if c.startswith(str(year))]].sum(axis=1)
    # Audit summary.
    peer_covered=raw.loc[raw.market_level!="No sampled peer","INN"].nunique()
    audit=[
        {"metric":"SKU rows","value":len(raw),"unit":"SKUs","note":"Unique Morion IDs"},
        {"metric":"INNs","value":raw.INN.nunique(),"unit":"molecules","note":"Development sample"},
        {"metric":"Monthly periods","value":len(month_cols),"unit":"months","note":"2019-01 to 2023-12"},
        {"metric":"Missing sales values","value":int(np.isnan(sales_matrix).sum()),"unit":"cells","note":"No imputation required"},
        {"metric":"Negative sales values","value":int((sales_matrix<0).sum()),"unit":"cells","note":"None observed"},
        {"metric":"Zero sales ratio","value":float((sales_matrix==0).mean()),"unit":"% of SKU-months","note":"Retained; may reflect unavailability/intermittency"},
        {"metric":"Strength extraction rate","value":float(raw.strength_value.notna().mean()),"unit":"% of SKUs","note":"Regex from Description"},
        {"metric":"Pack-size extraction rate","value":float(raw.pack_size.notna().mean()),"unit":"% of SKUs","note":"Regex from Description"},
        {"metric":"Potential stock-out gaps","value":stockout_count,"unit":"SKU-months","note":"Zero between two positive months"},
        {"metric":"Potential spikes","value":spike_count,"unit":"SKU-months","note":">5x local positive median and >50 units"},
        {"metric":"INNs with sampled peers","value":peer_covered,"unit":"INNs","note":"ATC4/ATC3 group has >=2 sampled INNs"},
    ]
    # Charts.
    save_annual_sales_chart(portfolio_annual,fig_dir/"01_annual_portfolio_sales.png")
    save_model_bars(forecast_rows,"test_WAPE","Forecast test WAPE: simpler baselines remain hard to beat",fig_dir/"02_forecast_model_wape.png",percent=True)
    save_model_bars(class_results,"test_lift_top20","Commercial opportunity model lift at top 20%",fig_dir/"03_classifier_lift.png",percent=False)
    portfolio_month_2023=pd.DataFrame({"month":[d.strftime("%Y-%m") for d in months[48:60]],"sales":actual_2023.sum(axis=1)})
    show_names=[selected_forecast]
    if selected_forecast!="Seasonal Naive":show_names.append("Seasonal Naive")
    preds_chart={n:test_preds[n].sum(axis=1) for n in show_names}
    save_forecast_chart(portfolio_month_2023,preds_chart,fig_dir/"04_forecast_2023_actual_vs_predicted.png")
    save_opportunity_matrix(kpi,fig_dir/"05_opportunity_matrix.png")
    save_pca_chart(kpi[["INN","pc1","pc2","cluster_label","sales_2023"]],fig_dir/"06_portfolio_clusters.png")
    # CSVs for auditability.
    kpi.sort_values("sales_2023",ascending=False).to_csv(output_dir/"inn_kpi.csv",index=False)
    peer_df.to_csv(output_dir/"market_peer_analysis.csv",index=False)
    monthly_export.to_csv(output_dir/"inn_monthly.csv",index=False)
    sku_export.to_csv(output_dir/"sku_features.csv",index=False)
    pd.DataFrame(forecast_monthly).to_csv(output_dir/"forecast_2024_monthly.csv",index=False)
    pd.DataFrame(class_results).to_csv(output_dir/"classification_model_results.csv",index=False)
    pd.DataFrame(forecast_rows).to_csv(output_dir/"forecast_model_results.csv",index=False)
    results={
        "metadata":{"input_file":str(input_path),"analysis_date":"2026-09-19","seed":SEED,"sales_unit":"pack-equivalent units; not revenue","source_url":"https://github.com/Marchev-Science/case-forecasting-pharmacutical-demand","selected_classification_model":selected_cls,"selected_forecast_model":selected_forecast,"forecast_ensemble_members":ensemble_members,"forecast_ensemble_weights":dict(zip(ensemble_members,weights.tolist()))},
        "audit":audit,
        "portfolio_annual":portfolio_annual.to_dict("records"),
        "inn_kpi":kpi.sort_values("sales_2023",ascending=False).to_dict("records"),
        "peer_analysis":peer_df.sort_values(["market_name","share_2023"],ascending=[True,False]).to_dict("records"),
        "cluster_validation":scores,
        "cluster_summary":cluster_summary.to_dict("records"),
        "classification_results":class_results,
        "classification_importance":importance[:15],
        "forecast_results":forecast_rows,
        "forecast_2024_monthly":forecast_monthly,
        "forecast_2023_portfolio":{"month":portfolio_month_2023["month"].tolist(),"actual":portfolio_month_2023["sales"].tolist(),**{n:test_preds[n].sum(axis=1).tolist() for n in test_preds}},
        "methodology_notes":[
            "Market-share estimates are sample shares, not external market shares.",
            "Peer share is reported only where an ATC4 or fallback ATC3 group contains at least two sampled INNs.",
            "The future-winner label uses the top quartile of six-month-ahead portfolio share change at each month because most sampled ATC markets lack enough peers.",
            "All model selection uses 2022 validation performance; 2023 is held out for final testing.",
            "The 2024 forecast is selected using validation results, refit on all 2019-2023 observations, and bottom-up reconciled by summing INN forecasts.",
            "Prediction intervals are empirical 80% ranges calibrated from 2022 log residuals; they do not include launch, price, promotion, supply-policy, or competitor-entry scenarios.",
        ],
        "sources":[
            {"name":"Teva pharmaceutical forecasting project","url":"https://github.com/Marchev-Science/case-forecasting-pharmacutical-demand"},
            {"name":"WHO ATC classification","url":"https://www.who.int/tools/atc-ddd-toolkit/atc-classification"},
            {"name":"IQVIA Brand and Portfolio Strategy","url":"https://www.iqvia.com/solutions/commercialization/brand-and-portfolio-strategy"},
        ],
    }
    (output_dir/"analysis_results.json").write_text(json.dumps(json_clean(results),ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output_dir":str(output_dir),"selected_classifier":selected_cls,"selected_forecast":selected_forecast,"top_2023":kpi.nlargest(5,"sales_2023")[["INN","sales_2023"]].to_dict("records"),"top_forecast_growth":kpi.nlargest(5,"forecast_growth_2024")[["INN","forecast_growth_2024","action_segment"]].to_dict("records"),"forecast_metrics":forecast_rows,"classification_metrics":class_results},ensure_ascii=False,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,default=Path("data/teva_sales_small.csv"))
    parser.add_argument("--output",type=Path,default=Path("outputs/iqvia_teva_case_20260919/analysis"))
    args=parser.parse_args(); main(args.input,args.output)
