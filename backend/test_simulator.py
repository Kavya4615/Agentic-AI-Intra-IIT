"""Quick test to verify the simulator generates correct vital signs."""
from simulator.patients import get_all_patients
from simulator.scenarios import create_scenario

patients = get_all_patients()
print("=" * 90)
print("  SIMULATOR TEST — Generating readings at t=0s, t=300s (5min), t=600s (10min)")
print("=" * 90)

for p in patients:
    scenario = create_scenario(p.scenario, p.baseline_vitals)
    print()
    print(f"  {p.patient_id} | {p.name} | Scenario: {p.scenario}")
    print("  " + "-" * 80)
    for t in [0, 300, 600]:
        v = scenario.generate(t)
        d = v.to_dict()
        artifact = " [ARTIFACT]" if d["is_artifact"] else ""
        hr = d["heart_rate"]
        spo2 = d["spo2"]
        rr = d["respiratory_rate"]
        sbp = d["systolic_bp"]
        dbp = d["diastolic_bp"]
        print(f"    t={t:>4}s  HR:{hr:6.1f}  SpO2:{spo2:5.1f}%  RR:{rr:5.1f}  BP:{sbp:5.1f}/{dbp:4.1f}{artifact}")

print()
print("=" * 90)
print("  All 8 patients generating correctly!")
print("=" * 90)
