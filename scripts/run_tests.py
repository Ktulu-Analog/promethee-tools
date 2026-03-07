#!/usr/bin/env python3
"""
scripts/run_tests.py — Lance tous les tests et génère un rapport de synthèse

Usage :
    python scripts/run_tests.py                    # tous les tests
    python scripts/run_tests.py --module data_file_tools
    python scripts/run_tests.py --verbose
    python scripts/run_tests.py --fail-fast
    python scripts/run_tests.py --rapport rapport.txt

Codes de retour :
    0 = tous les tests passent
    1 = au moins un test échoue ou erreur
"""

import argparse
import os
import sys
import time
import unittest
import io
from pathlib import Path
from datetime import datetime

# ── Setup path ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent

_CANDIDATES = [
    _REPO_ROOT.parent / "promethee",
    Path.home() / "promethee",
    Path.cwd(),
    Path.cwd().parent,
]
_PROMETHEE_ROOT = next((c for c in _CANDIDATES if (c / "core" / "tools_engine.py").exists()), None)

if _PROMETHEE_ROOT:
    sys.path.insert(0, str(_PROMETHEE_ROOT))
    print(f"✅ Prométhée trouvé : {_PROMETHEE_ROOT}")
else:
    # Générer le stub minimal
    stub_dir = _REPO_ROOT
    (stub_dir / "core").mkdir(exist_ok=True)
    stub_file = stub_dir / "core" / "tools_engine.py"
    if not stub_file.exists():
        stub_file.write_text(
            "_TOOLS = {}\n_TOOL_ICONS = {}\n_CURRENT_FAMILY = {}\n\n"
            "def set_current_family(m, l, e): _CURRENT_FAMILY['module'] = m\n\n"
            "def tool(name, description, parameters):\n"
            "    def decorator(func):\n"
            "        _TOOLS[name] = {'fn': func, 'schema': {}, 'parameters': parameters}\n"
            "        return func\n"
            "    return decorator\n"
        )
    sys.path.insert(0, str(stub_dir))
    print(f"⚠️  Prométhée non trouvé — stub minimal généré dans {stub_dir / 'core'}")

os.environ.setdefault("MAX_CONTEXT_TOKENS", "128000")

# ── Mapping module → fichier de test ─────────────────────────────────────────

MODULE_MAP = {
    "data_file_tools": "test_data_file_tools",
    "data_tools":      "test_data_tools",
    "system_tools":    "test_system_sql_python_export",
    "sql_tools":       "test_system_sql_python_export",
    "python_tools":    "test_system_sql_python_export",
    "export_tools":    "test_system_sql_python_export",
}

ALL_TEST_FILES = [
    "test_data_file_tools",
    "test_data_tools",
    "test_system_sql_python_export",
]

# ── Résultats enrichis ────────────────────────────────────────────────────────

class _DetailedResult(unittest.TextTestResult):
    """Capture les détails de chaque test pour le rapport final."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.results_detail = []
        self._start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self._start_times[test] = time.perf_counter()

    def _record(self, test, outcome, message=None):
        elapsed = round((time.perf_counter() - self._start_times.get(test, time.perf_counter())) * 1000, 1)
        parts = test.id().split(".")
        self.results_detail.append({
            "module":   parts[-3] if len(parts) >= 3 else "?",
            "classe":   parts[-2] if len(parts) >= 2 else "?",
            "methode":  parts[-1],
            "outcome":  outcome,
            "message":  message,
            "ms":       elapsed,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL", self._exc_info_to_string(err, test)[:300])

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR", self._exc_info_to_string(err, test)[:300])

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "SKIP", reason)


# ── Chargement des tests ──────────────────────────────────────────────────────

def load_suite(test_files: list[str], tests_dir: Path) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for tf in test_files:
        module_path = tests_dir / f"{tf}.py"
        if not module_path.exists():
            print(f"  ⚠️  Fichier de test introuvable : {module_path}")
            continue
        try:
            sys.path.insert(0, str(tests_dir))
            module = __import__(tf)
            suite.addTests(loader.loadTestsFromModule(module))
        except Exception as e:
            print(f"  ❌ Impossible de charger {tf} : {e}")

    return suite


# ── Rapport ───────────────────────────────────────────────────────────────────

def write_report(results: list[dict], suite_result: unittest.TestResult,
                 duree_total: float, output_path: str | None):
    """Génère un rapport texte structuré."""

    lines = []
    lines.append("=" * 70)
    lines.append(f"RAPPORT DE TESTS — Prométhée Tools")
    lines.append(f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    lines.append("")

    # Résumé global
    total   = len(results)
    passed  = sum(1 for r in results if r["outcome"] == "PASS")
    failed  = sum(1 for r in results if r["outcome"] == "FAIL")
    errors  = sum(1 for r in results if r["outcome"] == "ERROR")
    skipped = sum(1 for r in results if r["outcome"] == "SKIP")

    lines.append(f"RÉSUMÉ")
    lines.append(f"  Total    : {total}")
    lines.append(f"  ✅ Passés : {passed}")
    lines.append(f"  ❌ Échoués: {failed}")
    lines.append(f"  💥 Erreurs: {errors}")
    lines.append(f"  ⏭️  Ignorés: {skipped}")
    lines.append(f"  Durée    : {duree_total:.2f}s")
    lines.append("")

    # Par module
    modules: dict[str, list[dict]] = {}
    for r in results:
        modules.setdefault(r["module"], []).append(r)

    lines.append("PAR MODULE")
    lines.append("-" * 50)
    for mod_name, mod_results in sorted(modules.items()):
        p = sum(1 for r in mod_results if r["outcome"] == "PASS")
        f = sum(1 for r in mod_results if r["outcome"] in ("FAIL", "ERROR"))
        status = "✅" if f == 0 else "❌"
        lines.append(f"  {status} {mod_name:40} {p}/{len(mod_results)} passés")
    lines.append("")

    # Échecs et erreurs détaillés
    failures = [r for r in results if r["outcome"] in ("FAIL", "ERROR")]
    if failures:
        lines.append("DÉTAIL DES ÉCHECS")
        lines.append("-" * 50)
        for r in failures:
            lines.append(f"\n  [{r['outcome']}] {r['classe']}.{r['methode']}")
            if r["message"]:
                for line in r["message"].splitlines()[:8]:
                    lines.append(f"    {line}")
    else:
        lines.append("✅ Tous les tests passent.")
    lines.append("")

    # Tests les plus lents
    slow = sorted(results, key=lambda x: x["ms"], reverse=True)[:10]
    lines.append("TOP 10 TESTS LES PLUS LENTS")
    lines.append("-" * 50)
    for r in slow:
        lines.append(f"  {r['ms']:8.1f} ms  {r['classe']}.{r['methode']}")
    lines.append("")
    lines.append("=" * 70)

    report_text = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(report_text, encoding="utf-8")
        print(f"\n📄 Rapport sauvegardé : {output_path}")
    else:
        print("\n" + report_text)

    return report_text


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Lance les tests Prométhée Tools")
    parser.add_argument("--module",    default=None, help="Tester un module spécifique")
    parser.add_argument("--verbose",   action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--rapport",   default=None, help="Chemin du rapport de sortie")
    args = parser.parse_args()

    tests_dir = _REPO_ROOT / "tests"

    # Choisir les fichiers à charger
    if args.module:
        tf = MODULE_MAP.get(args.module)
        if not tf:
            print(f"❌ Module '{args.module}' inconnu. Modules disponibles : {list(MODULE_MAP.keys())}")
            sys.exit(1)
        test_files = [tf]
    else:
        test_files = ALL_TEST_FILES

    suite = load_suite(test_files, tests_dir)
    total_tests = suite.countTestCases()
    print(f"\n🔧 {total_tests} tests chargés depuis {len(test_files)} fichier(s)\n")

    # Lancer
    verbosity = 2 if args.verbose else 1
    stream = io.StringIO() if not args.verbose else sys.stderr

    runner = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=verbosity,
        resultclass=_DetailedResult,
        failfast=args.fail_fast,
    )

    t0 = time.perf_counter()
    result = runner.run(suite)
    duree = time.perf_counter() - t0

    # Rapport
    if hasattr(result, "results_detail"):
        write_report(result.results_detail, result, duree, args.rapport)

    # Code de retour
    success = result.wasSuccessful()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
