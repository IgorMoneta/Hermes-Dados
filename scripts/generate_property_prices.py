from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "inbox" / "property_prices.csv"


MARKETS = {
    ("Sao Paulo", "SP"): {
        "Pinheiros": (13500, -23.5614, -46.6820),
        "Vila Mariana": (11200, -23.5892, -46.6344),
        "Moema": (14500, -23.6000, -46.6650),
        "Tatuape": (9200, -23.5403, -46.5765),
        "Santana": (8500, -23.4977, -46.6252),
    },
    ("Rio de Janeiro", "RJ"): {
        "Copacabana": (12500, -22.9711, -43.1822),
        "Tijuca": (7600, -22.9249, -43.2322),
        "Barra da Tijuca": (10500, -23.0004, -43.3659),
        "Botafogo": (11800, -22.9511, -43.1809),
    },
    ("Belo Horizonte", "MG"): {
        "Savassi": (9800, -19.9368, -43.9334),
        "Pampulha": (7200, -19.8517, -43.9708),
        "Buritis": (6900, -19.9734, -43.9696),
    },
    ("Curitiba", "PR"): {
        "Batel": (10300, -25.4421, -49.2906),
        "Agua Verde": (7900, -25.4550, -49.2760),
        "Cabral": (8200, -25.4068, -49.2531),
    },
}


def generate(rows: int = 1800, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    market_rows = [
        (city, state, neighborhood, price_m2, latitude, longitude)
        for (city, state), neighborhoods in MARKETS.items()
        for neighborhood, (price_m2, latitude, longitude) in neighborhoods.items()
    ]
    selected = rng.choice(len(market_rows), rows)
    types = rng.choice(["Apartamento", "Casa", "Studio", "Cobertura"], rows, p=[0.58, 0.22, 0.12, 0.08])
    bedrooms = np.where(types == "Studio", 1, rng.integers(1, 6, rows))
    area = np.maximum(
        24,
        bedrooms * rng.normal(30, 7, rows)
        + np.where(types == "Casa", 55, 0)
        + np.where(types == "Cobertura", 80, 0),
    ).round(1)
    bathrooms = np.maximum(1, bedrooms + rng.integers(-1, 2, rows))
    parking = np.maximum(0, bedrooms - rng.integers(0, 3, rows))
    age = rng.integers(0, 46, rows)
    furnished = rng.choice(["Sim", "Nao"], rows, p=[0.28, 0.72])
    status = rng.choice(["Ativo", "Reservado", "Vendido"], rows, p=[0.72, 0.10, 0.18])
    dates = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 883, rows), unit="D")

    records = []
    for index, market_index in enumerate(selected):
        city, state, neighborhood, base_m2, latitude, longitude = market_rows[market_index]
        type_factor = {"Apartamento": 1.0, "Casa": 0.88, "Studio": 1.12, "Cobertura": 1.28}[types[index]]
        age_factor = max(0.72, 1 - age[index] * 0.006)
        furnishing_factor = 1.06 if furnished[index] == "Sim" else 1.0
        variation = rng.normal(1, 0.11)
        price_m2 = max(2500, base_m2 * type_factor * age_factor * furnishing_factor * variation)
        price = round(price_m2 * area[index] / 1000) * 1000
        records.append(
            {
                "id_imovel": f"IMO-{index + 1:05d}",
                "listing_date": dates[index].date().isoformat(),
                "city": city,
                "state": state,
                "neighborhood": neighborhood,
                "property_type": types[index],
                "area_m2": area[index],
                "bedrooms": int(bedrooms[index]),
                "bathrooms": int(bathrooms[index]),
                "parking_spaces": int(parking[index]),
                "age_years": int(age[index]),
                "floor": int(rng.integers(0, 31)) if types[index] != "Casa" else 0,
                "furnished": furnished[index],
                "condo_fee_brl": round(max(0, area[index] * rng.normal(8.5, 2.0))),
                "iptu_annual_brl": round(max(300, price * rng.normal(0.007, 0.0015))),
                "latitude": round(latitude + rng.normal(0, 0.008), 6),
                "longitude": round(longitude + rng.normal(0, 0.008), 6),
                "price_brl": float(price),
                "price_per_m2": round(price / area[index], 2),
                "status": status[index],
                "data_atualizacao": "2026-06-11",
            }
        )
    return pd.DataFrame(records)


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    dataset = generate()
    dataset.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
    print(f"{len(dataset)} registros gerados em {OUTPUT}")

