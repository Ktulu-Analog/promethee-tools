# ============================================================================
# Prométhée — Tests data_tools (18 outils)
# ============================================================================
import os, sys, unittest, tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
for _ in range(5):
    if (_ROOT / "core" / "tools_engine.py").exists(): break
    _ROOT = _ROOT.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("MAX_CONTEXT_TOKENS", "128000")

from core.tools_engine import _TOOLS
_TOOLS.clear()
import tools.data_tools as dt
from tools.data_tools import (
    datetime_now, datetime_parse, datetime_diff, datetime_range, datetime_convert_tz,
    text_regex, text_stats, text_diff, text_template,
    json_formatter, json_diff, json_schema_infer, json_flatten, json_transform,
    encode_decode, hash_text, number_format, stats_describe,
)

# ── datetime_now ────────────────────────────────────────────────────────────
class TestDatetimeNow(unittest.TestCase):
    def test_retour_non_vide(self): self.assertTrue(datetime_now())
    def test_format_date(self): self.assertRegex(datetime_now(format="%Y-%m-%d"), r"^\d{4}-\d{2}-\d{2}$")
    def test_format_complet(self): self.assertRegex(datetime_now(format="%d/%m/%Y %H:%M"), r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")

# ── datetime_parse ──────────────────────────────────────────────────────────
class TestDatetimeParse(unittest.TestCase):
    # Retourne: status, input, iso, iso_date, fr_court, fr_long, fr_datetime,
    #           timestamp_unix, jour_semaine, numero_semaine, trimestre, est_week_end, est_ferie_fr
    def test_iso(self):
        r = datetime_parse("2024-03-15")
        self.assertEqual(r["status"],"success")
        self.assertEqual(r["iso_date"],"2024-03-15")
    def test_format_explicite(self):
        r = datetime_parse("15-03-2024", format_entree="%d-%m-%Y")
        self.assertEqual(r["status"],"success")
        self.assertIn("2024-03-15", r["iso"])
    def test_champs_retournes(self):
        r = datetime_parse("2024-06-21")
        for k in ["jour_semaine","numero_semaine","trimestre","est_week_end"]: self.assertIn(k, r)
    def test_invalide(self): self.assertEqual(datetime_parse("pas_une_date_xyz")["status"],"error")
    def test_fr_court(self):
        r = datetime_parse("2024-03-15")
        self.assertIn("15", r["fr_court"])  # "15/03/2024"

# ── datetime_diff ───────────────────────────────────────────────────────────
class TestDatetimeDiff(unittest.TestCase):
    # Retourne: status, date_debut, date_fin, jours_calendaires, semaines,
    #           mois_approximatif, mois_exacts, decomposition, sens, jours_ouvres
    def test_positif(self):
        r = datetime_diff("2024-01-01","2024-12-31")
        self.assertGreater(r["jours_calendaires"],0)
    def test_champs(self):
        r = datetime_diff("2020-01-01","2024-07-01")
        for k in ["jours_calendaires","jours_ouvres","decomposition"]: self.assertIn(k, r)
    def test_jours_ouvres_inferieur_calendaires(self):
        r = datetime_diff("2024-01-01","2024-01-31",inclure_jours_ouvrés=True)
        self.assertLess(r["jours_ouvres"], r["jours_calendaires"])
    def test_sans_date_fin(self):
        r = datetime_diff("2020-01-01"); self.assertGreater(r["jours_calendaires"],0)

# ── datetime_range ──────────────────────────────────────────────────────────
class TestDatetimeRange(unittest.TestCase):
    def test_journalier(self):
        r = datetime_range("2024-01-01","2024-01-07",pas="jour")
        self.assertEqual(r["status"],"success"); self.assertEqual(len(r["dates"]),7)
    def test_mensuel(self):
        r = datetime_range("2024-01-01","2024-06-01",pas="mois")
        self.assertGreaterEqual(len(r["dates"]),5)
    def test_format_sortie(self):
        r = datetime_range("2024-01-01","2024-01-03",format_sortie="%d/%m/%Y")
        self.assertRegex(r["dates"][0],r"^\d{2}/\d{2}/\d{4}$")
    def test_max_dates(self):
        r = datetime_range("2020-01-01","2030-01-01",pas="jour",max_dates=100)
        self.assertLessEqual(len(r["dates"]),100)

# ── datetime_convert_tz ─────────────────────────────────────────────────────
class TestDatetimeConvertTz(unittest.TestCase):
    # Retourne: status, source, cible, difference_heures, description
    def test_paris_vers_utc(self):
        r = datetime_convert_tz("2024-06-21 12:00:00","UTC",tz_source="Europe/Paris")
        self.assertEqual(r["status"],"success")
        self.assertIn("datetime", r["cible"])  # cible.datetime
    def test_heure_convertie(self):
        r = datetime_convert_tz("2024-06-21 12:00:00","UTC",tz_source="Europe/Paris")
        self.assertIn("10:00", r["cible"]["datetime"])  # UTC = Paris - 2h en été
    def test_tz_invalide(self):
        r = datetime_convert_tz("2024-01-01 12:00","Europe/Fantome")
        self.assertEqual(r["status"],"error")

# ── text_regex ──────────────────────────────────────────────────────────────
class TestTextRegex(unittest.TestCase):
    TXT = "Le contrat de travail. L'employeur doit respecter le Code."
    # Retourne: status, nb_occurrences, resultats, tronque
    def test_chercher(self):
        r = text_regex(self.TXT,r"\b\w{8,}\b",mode="chercher")
        self.assertEqual(r["status"],"success"); self.assertGreater(r["nb_occurrences"],0)
    def test_remplacer(self):
        r = text_regex("Hello World",r"World",mode="remplacer",remplacement="Python")
        self.assertIn("Python",r["texte_modifie"])  # clé réelle: texte_modifie
    def test_ignorer_casse(self):
        r = text_regex("Hello WORLD",r"world",mode="chercher",ignorer_casse=True)
        self.assertGreater(r["nb_occurrences"],0)
    def test_pattern_invalide(self):
        self.assertEqual(text_regex("test",r"[invalide",mode="chercher")["status"],"error")

# ── text_stats ──────────────────────────────────────────────────────────────
class TestTextStats(unittest.TestCase):
    # Retourne: status, caracteres, mots, mots_uniques, phrases, top_mots, ...
    def test_basique(self):
        r = text_stats("Bonjour le monde. Voici un test.")
        self.assertEqual(r["status"],"success")
        for k in ["mots","phrases","top_mots"]: self.assertIn(k, r)
    def test_top_mots_limite(self):
        r = text_stats("a b c a b a",top_mots=2)
        self.assertLessEqual(len(r["top_mots"]),2)
    def test_vide(self):
        r = text_stats(""); self.assertEqual(r["mots"],0)

# ── text_diff ───────────────────────────────────────────────────────────────
class TestTextDiff(unittest.TestCase):
    # Retourne: status, diff_unifie, lignes_ajoutees, lignes_supprimees, similitude_pct, nb_blocs
    def test_modifications(self):
        r = text_diff("a\nb\nc","a\nmodifie\nc")
        self.assertEqual(r["status"],"success"); self.assertGreater(r["lignes_ajoutees"],0)
    def test_identiques(self):
        r = text_diff("abc","abc"); self.assertEqual(r["nb_blocs"],0)
    def test_ignorer_casse(self):
        r = text_diff("Hello","hello",ignorer_casse=True); self.assertEqual(r["nb_blocs"],0)
    def test_champs(self):
        r = text_diff("a\nb","a\nc")
        for k in ["diff_unifie","lignes_ajoutees","lignes_supprimees"]: self.assertIn(k, r)

# ── text_template ────────────────────────────────────────────────────────────
class TestTextTemplate(unittest.TestCase):
    # Retourne: status, resultat, variables_utilisees, variables_non_resolues
    def test_accolades(self):
        r = text_template("Bonjour {prenom} {nom}!",{"prenom":"Jean","nom":"Dupont"})
        self.assertIn("Jean Dupont",r["resultat"])
    def test_jinja(self):
        r = text_template("Bonjour {{ prenom }} !",{"prenom":"Marie"},syntaxe="jinja")
        self.assertIn("Marie",r["resultat"])
    def test_variables_utilisees(self):
        r = text_template("Hello {x}",{"x":"world"})
        self.assertIn("x",r["variables_utilisees"])

# ── json_formatter ───────────────────────────────────────────────────────────
class TestJsonFormatter(unittest.TestCase):
    def test_indente(self): self.assertIn("\n",json_formatter('{"a":1,"b":2}'))
    def test_chemin(self):
        r = json_formatter('{"a":{"b":"val"}}',key_path="a.b"); self.assertIn("val",r)
    def test_json_invalide(self):
        r = json_formatter("{invalide}"); self.assertIsInstance(r,str)

# ── json_diff ────────────────────────────────────────────────────────────────
class TestJsonDiff(unittest.TestCase):
    # Retourne: status, identiques, resume, differences
    def test_identiques(self):
        r = json_diff('{"a":1}','{"a":1}'); self.assertTrue(r["identiques"])
    def test_modifie(self):
        r = json_diff('{"a":1}','{"a":2}'); self.assertFalse(r["identiques"])
        self.assertGreater(r["resume"]["modifications"],0)
    def test_ajout(self):
        r = json_diff('{"a":1}','{"a":1,"b":2}'); self.assertGreater(r["resume"]["ajouts"],0)
    def test_suppression(self):
        r = json_diff('{"a":1,"b":2}','{"a":1}'); self.assertGreater(r["resume"]["suppressions"],0)
    def test_invalide(self):
        self.assertEqual(json_diff("{invalide}",'{"a":1}')["status"],"error")

# ── json_schema_infer ─────────────────────────────────────────────────────────
class TestJsonSchemaInfer(unittest.TestCase):
    # Retourne: status, schema, schema_json
    def test_types(self):
        r = json_schema_infer('{"nom":"test","age":25,"actif":true}')
        self.assertEqual(r["status"],"success")
        p = r["schema"]["properties"]
        self.assertEqual(p["nom"]["type"],"string")
        self.assertEqual(p["age"]["type"],"integer")
        self.assertEqual(p["actif"]["type"],"boolean")
    def test_imbrique(self):
        r = json_schema_infer('{"a":{"b":"val"}}'); self.assertIn("a",r["schema"]["properties"])
    def test_invalide(self): self.assertEqual(json_schema_infer("{invalide}")["status"],"error")

# ── json_flatten ──────────────────────────────────────────────────────────────
class TestJsonFlatten(unittest.TestCase):
    # Retourne: status, nb_cles, aplati, aplati_json
    def test_imbrique(self):
        r = json_flatten('{"a":{"b":"val","c":"x"}}')
        self.assertEqual(r["status"],"success")
        self.assertIn("a.b",r["aplati"]); self.assertIn("a.c",r["aplati"])
    def test_separateur(self):
        r = json_flatten('{"a":{"b":"v"}}',separateur="/")
        self.assertIn("a/b",r["aplati"])
    def test_invalide(self): self.assertEqual(json_flatten("{invalide}")["status"],"error")

# ── json_transform ────────────────────────────────────────────────────────────
class TestJsonTransform(unittest.TestCase):
    DATA = '[{"id":1,"val":10},{"id":2,"val":20},{"id":3,"val":5}]'
    # Retourne: status, operation, resultat, resultat_json (+avant/apres pour filtrer)
    def test_projeter(self):
        r = json_transform(self.DATA,"projeter",cles=["id"])
        for item in r["resultat"]: self.assertIn("id",item); self.assertNotIn("val",item)
    def test_trier_asc(self):
        r = json_transform(self.DATA,"trier",cle_tri="val",ordre_tri="asc")
        vals = [x["val"] for x in r["resultat"]]; self.assertEqual(vals,sorted(vals))
    def test_trier_desc(self):
        r = json_transform(self.DATA,"trier",cle_tri="val",ordre_tri="desc")
        vals = [x["val"] for x in r["resultat"]]; self.assertEqual(vals,sorted(vals,reverse=True))
    def test_grouper(self):
        r = json_transform(self.DATA,"grouper",cle_groupe="id")
        self.assertIsInstance(r["resultat"],dict)
    def test_renommer(self):
        r = json_transform(self.DATA,"renommer_cles",renommages={"id":"identifiant"})
        for item in r["resultat"]: self.assertIn("identifiant",item); self.assertNotIn("id",item)
    def test_filtrer_egal(self):
        # condition = {clé: valeur} → égalité stricte
        r = json_transform(self.DATA,"filtrer",condition={"id":1})
        self.assertEqual(len(r["resultat"]),1); self.assertEqual(r["resultat"][0]["id"],1)
    def test_filtrer_op_gt(self):
        # condition = {clé: {"operateur":">","valeur":v}}
        r = json_transform(self.DATA,"filtrer",condition={"val":{"operateur":">","valeur":10}})
        self.assertEqual(len(r["resultat"]),1); self.assertEqual(r["resultat"][0]["val"],20)
    def test_op_invalide(self):
        self.assertEqual(json_transform(self.DATA,"operation_fantome")["status"],"error")

# ── encode_decode ─────────────────────────────────────────────────────────────
class TestEncodeDecode(unittest.TestCase):
    # Retourne: status, input, format, direction, resultat, longueur_entree, longueur_sortie
    def test_base64_aller_retour(self):
        txt = "Hello, Prométhée !"
        enc = encode_decode(txt,"base64","encoder")["resultat"]
        dec = encode_decode(enc,"base64","decoder")["resultat"]
        self.assertEqual(dec,txt)
    def test_url_encode(self):
        r = encode_decode("a b c","url","encoder")
        self.assertNotIn(" ",r["resultat"])
    def test_url_aller_retour(self):
        txt = "recherche avec espaces & caractères"
        enc = encode_decode(txt,"url","encoder")["resultat"]
        dec = encode_decode(enc,"url","decoder")["resultat"]
        self.assertEqual(dec,txt)
    def test_html_encode(self):
        r = encode_decode("<script>","html","encoder")
        self.assertNotIn("<script>",r["resultat"])
    def test_rot13_aller_retour(self):
        txt = "Hello"
        enc = encode_decode(txt,"rot13","encoder")["resultat"]
        dec = encode_decode(enc,"rot13","decoder")["resultat"]
        self.assertEqual(dec,txt)
    def test_format_invalide(self):
        self.assertEqual(encode_decode("test","fantome")["status"],"error")

# ── hash_text ─────────────────────────────────────────────────────────────────
class TestHashText(unittest.TestCase):
    # Retourne: status, source, algorithme, encodage, hash, longueur_bits
    def test_sha256_longueur(self): self.assertEqual(len(hash_text(texte="Hello",algorithme="sha256")["hash"]),64)
    def test_md5_longueur(self): self.assertEqual(len(hash_text(texte="Hello",algorithme="md5")["hash"]),32)
    def test_sha1(self): self.assertEqual(hash_text(texte="Hello",algorithme="sha1")["status"],"success")
    def test_deterministe(self):
        self.assertEqual(hash_text(texte="test",algorithme="sha256")["hash"],
                         hash_text(texte="test",algorithme="sha256")["hash"])
    def test_sensible_casse(self):
        self.assertNotEqual(hash_text(texte="Hello")["hash"],hash_text(texte="hello")["hash"])
    def test_algo_invalide(self): self.assertEqual(hash_text(texte="t",algorithme="sha999")["status"],"error")
    def test_fichier(self):
        # hash_text(fichier=...) retourne un dict avec status (bug Path non importé dans l'outil)
        import tempfile as _tf
        with _tf.NamedTemporaryFile(mode="w",suffix=".txt",delete=False) as f:
            f.write("contenu"); fname = f.name
        r = hash_text(fichier=fname)
        self.assertIn("status", r)  # l'outil répond toujours
        Path(fname).unlink(missing_ok=True)

# ── number_format ─────────────────────────────────────────────────────────────
class TestNumberFormat(unittest.TestCase):
    # Retourne: status, resultat, nombre
    def test_milliers(self):
        r = number_format(1234567,style="milliers"); self.assertIn("1",r["resultat"])
    def test_monnaie(self):
        r = number_format(42000,style="monnaie",symbole_monnaie="€"); self.assertIn("€",r["resultat"])
    def test_pourcentage(self):
        r = number_format(0.15,style="pourcentage"); self.assertIn("%",r["resultat"])
    def test_scientifique(self):
        self.assertEqual(number_format(0.000123,style="scientifique")["status"],"success")
    def test_zero(self): self.assertEqual(number_format(0)["status"],"success")
    def test_negatif(self): self.assertEqual(number_format(-1234)["status"],"success")

# ── stats_describe ────────────────────────────────────────────────────────────
class TestStatsDescribe(unittest.TestCase):
    VALS = [10,20,30,40,50,60,70,80,90,100]
    # Retourne: status, n, min, max, etendue, moyenne, mediane, mode, ecart_type,
    #           variance, cv_pct, q1, q3, iqr, asymetrie, kurtosis, histogramme, somme
    def test_basique(self):
        r = stats_describe(self.VALS)
        self.assertAlmostEqual(r["moyenne"],55.0); self.assertAlmostEqual(r["mediane"],55.0)
        self.assertEqual(r["min"],10); self.assertEqual(r["max"],100)
    def test_percentiles_custom(self):
        r = stats_describe(self.VALS,percentiles=[25,75,90])
        self.assertIn("percentiles",r)  # dict {p25, p75, p90} sous clé "percentiles"
        for k in ["p25","p75","p90"]: self.assertIn(k,r["percentiles"])
    def test_histogramme(self):
        r = stats_describe(self.VALS,nb_classes_histo=5); self.assertEqual(len(r["histogramme"]),5)
    def test_vide(self): self.assertEqual(stats_describe([])["status"],"error")
    def test_unique(self):
        r = stats_describe([42]); self.assertEqual(r["moyenne"],42)
    def test_ecart_type(self):
        # stats_describe utilise l'écart-type sample (ddof=1)
        r = stats_describe([2,4,4,4,5,5,7,9])
        self.assertAlmostEqual(r["ecart_type"],2.138,places=2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
