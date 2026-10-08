"""Shared settings for the Mise pipeline.

Everything that describes the (synthetic) business lives here, so a reader can
change one number and re-run the pipeline.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"
DASH_DIR = ROOT / "dashboard"

SEED = 7

AREA = "Bengaluru South-East"
KITCHENS = ["Koramangala", "HSR Layout", "Indiranagar", "Whitefield", "Bellandur",
            "Electronic City", "JP Nagar", "Jayanagar", "Marathahalli", "Hebbal"]
# relative size of each kitchen's catchment
KITCHEN_SIZE = [1.25, 1.10, 1.15, 1.05, 1.00, 0.95, 0.95, 1.00, 0.98, 0.90]

BRANDS = ["EatFit", "Olio Pizza", "Sharief Bhai", "CakeZone", "Frozen Bottle", "Millet Express"]
SLOTS = ["Breakfast", "Lunch", "Snacks", "Dinner", "Late night"]
SLOT_HOURS = ["8-11 am", "12-3 pm", "4-7 pm", "7-11 pm", "11 pm-2 am"]
SLOT_START_HOUR = [8, 12, 16, 19, 23]
SLOT_LEN_MIN = [180, 180, 180, 240, 180]

# average orders per slot for a size-1.0 kitchen on a weekday
SLOT_BASE = [16, 70, 24, 86, 22]
# share of each brand within a slot (rows = slots, columns = brands)
BRAND_SHARE = [
    [0.45, 0.00, 0.00, 0.10, 0.05, 0.40],
    [0.48, 0.12, 0.25, 0.03, 0.02, 0.10],
    [0.15, 0.20, 0.10, 0.30, 0.20, 0.05],
    [0.18, 0.30, 0.32, 0.10, 0.06, 0.04],
    [0.02, 0.25, 0.28, 0.30, 0.15, 0.00],
]
# hands-on minutes of work for one order of each brand on the line
BRAND_WORK_MIN = [5.5, 8.0, 6.5, 3.5, 2.5, 6.0]
# average order value in rupees
BRAND_AOV = [245, 420, 360, 520, 210, 190]

# cooks normally rostered per slot
COOKS = [2, 4, 3, 4, 2]

BREAK_EVEN_ORDERS = 180     # orders per kitchen per day (founder interview)
STRONG_ORDERS = 250
PROMISE_MIN = 15            # food-ready promise to delivery apps

START_DATE = "2026-08-14"   # 8 weeks of history
END_DATE = "2026-10-08"     # last complete day ("yesterday")
TEST_DAYS = 7               # last week is held out to test the models
TOMORROW = "2026-10-09"

DEFECTS = ["Late delivery", "Missing item", "Wrong item", "Taste or quality",
           "Cold food", "Packaging or spill", "Quantity"]
# tags the pipeline can assign: the defects, plus "Needs review" when keyword rules cannot read a complaint
TAGS = DEFECTS + ["Needs review"]

# what each brand's order needs from prep, per order: (item, unit, quantity)
PREP_RECIPE = {
    "EatFit": [("Dal and sabzi base", "kg", 0.18), ("Multigrain roti dough", "kg", 0.12), ("Brown rice, cooked", "kg", 0.15)],
    "Olio Pizza": [("Pizza dough balls", "pcs", 1.3), ("Pizza sauce", "kg", 0.08), ("Garlic dip cups", "pcs", 1.0)],
    "Sharief Bhai": [("Biryani masala base", "kg", 0.14), ("Marinated chicken", "kg", 0.20), ("Raita cups", "pcs", 1.0)],
    "CakeZone": [("Cake bases, 500 g", "pcs", 0.6), ("Whipped cream", "kg", 0.05)],
    "Frozen Bottle": [("Ice-cream mix", "L", 0.25), ("Syrups", "L", 0.03)],
    "Millet Express": [("Millet dosa batter", "kg", 0.16), ("Sambar", "L", 0.20), ("Chutney cups", "pcs", 2.0)],
}
