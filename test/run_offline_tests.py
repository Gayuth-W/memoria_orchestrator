"""Run all offline tests with one command, from anywhere:  python run_offline_tests.py

No Ollama, no memoria, no env needed. Handles sys.path so you don't have to set
PYTHONPATH (the reason `python test/test_x.py` fails directly).
"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # so `from app import ...` works

OFFLINE = [
    "test_generate_wiring", "test_memoria_client", "test_orchestrator_wiring",
    "test_extraction_wiring", "test_pinning_wiring", "test_server",
]

failures = []
for name in OFFLINE:
    path = os.path.join(ROOT, "test", name + ".py")
    spec = importlib.util.spec_from_file_location("offline_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    print("\n" + "#" * 60 + f"\n# {name}\n" + "#" * 60)
    spec.loader.exec_module(mod)
    rc = mod.main()
    if rc != 0:
        failures.append(name)

print("\n" + "=" * 60)
print("ALL OFFLINE TESTS PASSED" if not failures else "FAILED: " + ", ".join(failures))
sys.exit(1 if failures else 0)