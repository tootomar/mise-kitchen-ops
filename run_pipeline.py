"""Run the whole Mise pipeline with one command:

    python run_pipeline.py

1. generate data   2. forecast + prep plan   3. prep-time model + staffing what-if
4. tag complaints + find hotspots   5. build dashboard/index.html   6. write alerts
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mise import generate_data, forecast, prep_time, complaints, build_dashboard, alerts  # noqa: E402


def main():
    t0 = time.time()
    print("1/6  Generating 8 weeks of synthetic orders ...")
    print("     ", generate_data.generate())
    print("2/6  Training the demand forecast and testing it on the last 7 days ...")
    fc = forecast.run()
    print(f"      error (WAPE) {fc['wape_model']:.1%} vs {fc['wape_baseline']:.1%} for 'same as last week'")
    print("3/6  Training the prep-time model and running tomorrow's staffing what-if ...")
    pt = prep_time.run(fc["tomorrow"])
    print(f"      average error {pt['mae_model']:.2f} min vs {pt['mae_baseline']:.2f} min for 'usual time'")
    print("4/6  Tagging complaints and finding hotspots ...")
    cp = complaints.run()
    print(f"      tagged with {cp['method']}: {cp['accuracy']:.1%} match with reviewer labels; {len(cp['hotspots'])} hotspots")
    print("5/6  Building the dashboard ...")
    build_dashboard.build(fc, pt, cp)
    print("6/6  Writing this morning's alerts (send them with: python send_alerts.py) ...")
    al = alerts.run(send_messages=False)["alerts"]
    print(f"      {sum(a['severity'] == 'critical' for a in al)} critical, {sum(a['severity'] != 'critical' for a in al)} warnings")
    print(f"Done in {time.time() - t0:.0f}s. Open dashboard/index.html in a browser.")


if __name__ == "__main__":
    main()
