"""Does each concentrate dissolve? Stock strength against sourced solubility at the entered temperature.

Stock strength is the product's grams per litre of final solution times the injection ratio. The limit is grams of
product (as sold, hydrate water included) per litre of stock, interpolated linearly between the nearest sourced
temperature points; outside them, or for a product without a record, the row is ``not_checked``, never passed.

Records (``data/solubility.json``, sourced values approved by the owner on 2026-10-23) are
``{"product": catalogue name, "points": [[degC, g/L], ...], "source": citation, "notes": ...}``. Without that file
every product is ``not_checked``.

Limitation: each product is checked alone, as a single salt in pure water. Products sharing a tank (common ions such
as K+ or SO4--) dissolve less together.
"""
from dataclasses import dataclass
import json
from pathlib import Path

TABLE_PATH = Path(__file__).with_name('data') / 'solubility.json'
SINGLE_SALT = ('single-salt solubility in pure water; products sharing a tank dissolve less together '
               '(no mixed-salt data, no safety margin)')


@dataclass(frozen=True)
class SolubilityRow:
    tank: str
    product: str
    stock_g_per_l: float
    limit_g_per_l: float | None
    status: str                 # 'ok', 'exceeds' or 'not_checked'
    source: str | None


def load_solubility_table(path=TABLE_PATH):
    """Records from ``path``; an empty list when the file does not exist."""
    path = Path(path)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def limit_at(points, temperature_c):
    """Linear interpolation between the nearest points; ``None`` outside them."""
    points = sorted(points)
    for (t0, g0), (t1, g1) in zip(points, points[1:]):
        if t0 <= temperature_c <= t1:
            return g0 if temperature_c == t0 else g1 if temperature_c == t1 else \
                g0 + (g1 - g0) * (temperature_c - t0) / (t1 - t0)
    return points[0][1] if len(points) == 1 and points[0][0] == temperature_c else None


def check_stock_solubility(tanks, ratio, temperature_c, *, table=None):
    """One row per product in ``tanks`` (``ConcentrateTank``) at 1:``ratio`` and ``temperature_c``."""
    records = {r['product']: r for r in (load_solubility_table() if table is None else table)}
    found = []
    for tank in tanks:
        for product in tank.products:
            stock = product.grams_per_litre * ratio
            record = records.get(product.name)
            limit = None if record is None else limit_at(record['points'], temperature_c)
            status = 'not_checked' if limit is None else 'exceeds' if stock > limit else 'ok'
            found.append(SolubilityRow(tank.name, product.name, stock, limit, status,
                                       None if limit is None else record['source']))
    return found


def exceeds_message(row, temperature_c):
    return (f'{row.product} does not dissolve in tank {row.tank}: {row.stock_g_per_l:.4g} g/L needed, '
            f'{row.limit_g_per_l:.4g} g/L at {temperature_c:g} °C')
