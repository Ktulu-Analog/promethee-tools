# ============================================================================
# Prométhée — Tests data_file_tools (21 outils)
# ============================================================================
import os, sys, tempfile, unittest
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent
for _ in range(5):
    if (_ROOT / "core" / "tools_engine.py").exists(): break
    _ROOT = _ROOT.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("MAX_CONTEXT_TOKENS", "128000")

import pandas as pd
import numpy as np

from core.tools_engine import _TOOLS
_TOOLS.clear()
import tools.data_file_tools as _dft_mod
from tools.data_file_tools import (
    df_read, df_list, df_head, df_info, df_value_counts,
    df_groupby, df_correlate, df_outliers,
    df_query, df_pivot, df_merge, df_concat,
    df_clean, df_cast, df_apply, df_rename, df_sample,
    df_anonymize, df_write, df_drop, _DATASETS,
)

def _inject(name, df):
    _DATASETS[name] = {"df": df, "source": "test", "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def _rh():
    return pd.DataFrame({
        "nom":            ["Dupont","Martin","Durand","Petit","Leroy","Simon"],
        "service":        ["RH","IT","RH","IT","Finance","Finance"],
        "salaire":        [42000,58000,39000,62000,51000,47000],
        "age":            [35,28,45,32,41,38],
        "date_entree":    pd.to_datetime(["2018-03-15","2015-09-01","2021-11-20","2019-06-01","2016-04-10","2020-02-28"]),
        "date_naissance": pd.to_datetime(["1989-07-22","1996-03-10","1979-08-05","1992-12-15","1983-05-30","1986-11-03"]),
        "note":           [4.2,3.8,4.5,4.1,3.9,4.0],
    })

class _Base(unittest.TestCase):
    def setUp(self):    _DATASETS.clear(); _inject("rh", _rh())
    def tearDown(self): _DATASETS.clear()


# ── df_read ────────────────────────────────────────────────────────────────
class TestDfRead(unittest.TestCase):
    def setUp(self):
        _DATASETS.clear()
        self.tmp = tempfile.mkdtemp()
    def tearDown(self): _DATASETS.clear()
    def _csv(self, name="t.csv", content=None):
        p = os.path.join(self.tmp, name)
        Path(p).write_text(content or "nom,age,salaire\nDupont,35,42000\nMartin,28,58000\n", encoding="utf-8")
        return p
    def test_csv_basique(self):
        r = df_read(self._csv(), nom="t")
        self.assertEqual(r["status"], "success")
        self.assertEqual(r["nb_lignes"], 2); self.assertEqual(r["nb_colonnes"], 3)
        self.assertIn("t", _DATASETS)
    def test_csv_separateur_semicolon(self):
        r = df_read(self._csv("semi.csv","a;b;c\n1;2;3\n4;5;6\n"), nom="semi")
        self.assertEqual(r["status"], "success"); self.assertEqual(r["nb_colonnes"], 3)
    def test_csv_separateur_tab(self):
        r = df_read(self._csv("tab.csv","a\tb\tc\n1\t2\t3\n"), nom="tab")
        self.assertEqual(r["status"], "success"); self.assertEqual(r["nb_colonnes"], 3)
    def test_nom_par_defaut(self):
        r = df_read(self._csv("employes.csv"))
        self.assertEqual(r["nom"], "employes"); self.assertIn("employes", _DATASETS)
    def test_excel_xlsx(self):
        p = os.path.join(self.tmp, "xl.xlsx")
        pd.DataFrame({"a":[1,2],"b":[3,4]}).to_excel(p, index=False)
        r = df_read(p, nom="xl")
        self.assertEqual(r["status"], "success"); self.assertEqual(r["nb_lignes"], 2)
    def test_excel_feuille(self):
        p = os.path.join(self.tmp, "m.xlsx")
        with pd.ExcelWriter(p, engine="openpyxl") as w:
            pd.DataFrame({"x":[1]}).to_excel(w, sheet_name="F1", index=False)
            pd.DataFrame({"y":[2]}).to_excel(w, sheet_name="F2", index=False)
        r = df_read(p, nom="m", feuille="F2")
        self.assertEqual(r["status"], "success"); self.assertEqual(r["feuille_chargee"], "F2")
        self.assertIn("F1", r["feuilles_disponibles"])
    def test_colonnes_retournees(self):
        r = df_read(self._csv(), nom="t3")
        self.assertEqual(sorted(r["colonnes"]), sorted(["nom","age","salaire"]))
    def test_introuvable(self):
        r = df_read("/tmp/xyz_inexistant_123.csv", nom="x")
        self.assertEqual(r["status"], "error")
    def test_format_non_supporte(self):
        p = os.path.join(self.tmp, "f.parquet"); Path(p).write_bytes(b"fake")
        r = df_read(p, nom="x"); self.assertEqual(r["status"], "error")

# ── df_list ────────────────────────────────────────────────────────────────
class TestDfList(unittest.TestCase):
    def setUp(self):    _DATASETS.clear()
    def tearDown(self): _DATASETS.clear()
    def test_vide(self):
        r = df_list()
        self.assertEqual(r["status"],"success"); self.assertEqual(r["nombre"],0)
    def test_plusieurs(self):
        _inject("a", pd.DataFrame({"x":[1,2]})); _inject("b", pd.DataFrame({"y":[3,4,5]}))
        r = df_list(); self.assertEqual(r["nombre"],2)
        noms = [d["nom"] for d in r["datasets"]]
        self.assertIn("a", noms); self.assertIn("b", noms)
    def test_nb_lignes_dans_info(self):
        _inject("rh", _rh()); r = df_list()
        self.assertEqual(r["datasets"][0]["nb_lignes"], 6)

# ── df_head ────────────────────────────────────────────────────────────────
class TestDfHead(_Base):
    def test_debut(self):
        r = df_head("rh", n=3)
        self.assertEqual(r["status"],"success"); self.assertEqual(r["affichees"],3); self.assertEqual(r["sens"],"début")
    def test_fin(self):
        r = df_head("rh", n=-2)
        self.assertEqual(r["sens"],"fin"); self.assertEqual(r["affichees"],2)
    def test_colonnes(self):
        r = df_head("rh", n=2, colonnes=["nom","salaire"])
        for l in r["lignes"]: self.assertIn("nom",l); self.assertNotIn("age",l)
    def test_colonne_inexistante(self):
        r = df_head("rh", colonnes=["fantome"]); self.assertEqual(r["status"],"error")
    def test_dataset_inexistant(self):
        r = df_head("inexistant"); self.assertEqual(r["status"],"error")
        self.assertIn("rh", r["error"])

# ── df_info ────────────────────────────────────────────────────────────────
class TestDfInfo(_Base):
    def test_stats_numeriques(self):
        r = df_info("rh"); self.assertEqual(r["status"],"success"); self.assertEqual(r["nb_lignes"],6)
        col = next(c for c in r["colonnes"] if c["colonne"]=="salaire")
        for k in ["min","max","moyenne"]: self.assertIn(k, col)
    def test_filtre_colonnes(self):
        r = df_info("rh", colonnes=["salaire","age"]); self.assertEqual(len(r["colonnes"]),2)
    def test_doublons(self):
        _inject("dup", pd.DataFrame({"a":[1,1,2],"b":["x","x","y"]}))
        self.assertEqual(df_info("dup")["nb_doublons"],1)
    def test_top_valeurs_texte(self):
        r = df_info("rh", colonnes=["service"]); self.assertIn("top_valeurs", r["colonnes"][0])

# ── df_value_counts ────────────────────────────────────────────────────────
class TestDfValueCounts(_Base):
    def test_basique(self):
        r = df_value_counts("rh","service"); self.assertEqual(r["status"],"success")
        self.assertEqual(sum(x["occurrences"] for x in r["resultats"]), 6)
    def test_normaliser(self):
        r = df_value_counts("rh","service",normaliser=True)
        for e in r["resultats"]: self.assertIn("pourcentage",e)
    def test_limite(self):
        r = df_value_counts("rh","service",limite=2); self.assertLessEqual(len(r["resultats"]),2)
    def test_inclure_nan(self):
        _inject("n", pd.DataFrame({"x":["a","b",None,"a"]}))
        self.assertGreater(df_value_counts("n","x",inclure_nan=True)["nb_manquants"],0)
    def test_colonne_inexistante(self):
        self.assertEqual(df_value_counts("rh","fantome")["status"],"error")

# ── df_groupby ─────────────────────────────────────────────────────────────
class TestDfGroupby(_Base):
    def test_sum(self):
        r = df_groupby("rh",["service"],{"salaire":"sum"})
        self.assertEqual(r["status"],"success"); self.assertEqual(r["nb_groupes"],3)
        self.assertIn("salaire", r["colonnes"])  # nom original quand 1 seule fonction
    def test_multi_agg(self):
        r = df_groupby("rh",["service"],{"salaire":["sum","mean"],"age":"median"})
        self.assertEqual(r["status"],"success")
        for c in ["salaire_sum","salaire_mean","age_median"]: self.assertIn(c, r["colonnes"])
    def test_tri_desc(self):
        r = df_groupby("rh",["service"],{"salaire":"sum"},trier_par=["salaire"],ordre_desc=True)
        vals = [l["salaire"] for l in r["lignes"]]
        self.assertEqual(vals, sorted(vals, reverse=True))
    def test_sauvegarde(self):
        df_groupby("rh",["service"],{"salaire":"sum"},sauvegarder_sous="masse")
        self.assertIn("masse",_DATASETS); self.assertEqual(len(_DATASETS["masse"]["df"]),3)
    def test_colonne_inexistante(self):
        self.assertEqual(df_groupby("rh",["fantome"],{"salaire":"sum"})["status"],"error")
    def test_agregation_invalide(self):
        self.assertEqual(df_groupby("rh",["service"],{"salaire":"variance"})["status"],"error")
    def test_toutes_fonctions(self):
        for fn in ["sum","mean","count","min","max","median","std","nunique","first","last"]:
            r = df_groupby("rh",["service"],{"salaire":fn})
            self.assertEqual(r["status"],"success", f"agg={fn} → {r.get('error')}")

# ── df_correlate ───────────────────────────────────────────────────────────
class TestDfCorrelate(_Base):
    def test_pearson(self):
        r = df_correlate("rh"); self.assertEqual(r["status"],"success")
        self.assertIn("matrice",r); self.assertIn("top_paires",r)
    def test_spearman(self): self.assertEqual(df_correlate("rh",methode="spearman")["status"],"success")
    def test_kendall(self):  self.assertEqual(df_correlate("rh",methode="kendall")["status"],"success")
    def test_filtre_colonnes(self):
        r = df_correlate("rh",colonnes=["salaire","age"])
        self.assertEqual(r["nb_colonnes"],2); self.assertEqual(r["nb_paires_total"],1)
    def test_seuil(self):
        self.assertGreaterEqual(df_correlate("rh",seuil=0.0)["nb_paires_total"],
                                df_correlate("rh",seuil=0.99)["nb_paires_total"])
    def test_intensite_sens(self):
        for p in df_correlate("rh")["top_paires"]:
            self.assertIn(p["intensite"],["forte","modérée","faible"])
            self.assertIn(p["sens"],["positive","négative"])
    def test_methode_invalide(self):   self.assertEqual(df_correlate("rh",methode="cosine")["status"],"error")
    def test_sans_numeriques(self):
        _inject("t",pd.DataFrame({"a":["x","y"],"b":["p","q"]}))
        self.assertEqual(df_correlate("t")["status"],"error")

# ── df_outliers ────────────────────────────────────────────────────────────
class TestDfOutliers(_Base):
    def setUp(self):
        super().setUp()
        df = _rh().copy()
        df.loc[len(df)] = ["Out","RH",999999,35,pd.Timestamp("2020-01-01"),pd.Timestamp("1988-01-01"),4.0]
        _inject("rh_out", df)
    def test_iqr_detecte(self):
        r = df_outliers("rh_out",colonnes=["salaire"],methode="iqr")
        self.assertGreater(r["nb_outliers"],0); self.assertIn(999999,[l["salaire"] for l in r["lignes"]])
    def test_zscore(self):
        r = df_outliers("rh_out",colonnes=["salaire"],methode="zscore",seuil_z=2.0)
        self.assertGreater(r["nb_outliers"],0)
    def test_k_strict(self):
        self.assertGreaterEqual(df_outliers("rh_out",methode="iqr",k=1.5)["nb_outliers"],
                                df_outliers("rh_out",methode="iqr",k=3.0)["nb_outliers"])
    def test_sauvegarde(self):
        df_outliers("rh_out",colonnes=["salaire"],sauvegarder_sous="anom")
        self.assertIn("anom",_DATASETS)
    def test_methode_invalide(self): self.assertEqual(df_outliers("rh",methode="lof")["status"],"error")
    def test_sans_numeriques(self):
        _inject("t",pd.DataFrame({"a":["x","y"]})); self.assertEqual(df_outliers("t")["status"],"error")

# ── df_query ───────────────────────────────────────────────────────────────
class TestDfQuery(_Base):
    def test_filtre_num(self):
        r = df_query("rh",filtre="salaire > 50000")
        for l in r["lignes"]: self.assertGreater(l["salaire"],50000)
    def test_filtre_str(self):
        self.assertEqual(df_query("rh",filtre='service == "IT"')["nb_lignes"],2)
    def test_colonnes(self):
        r = df_query("rh",colonnes=["nom","salaire"])
        for l in r["lignes"]: self.assertIn("nom",l); self.assertNotIn("age",l)
    def test_tri_asc(self):
        vals = [l["salaire"] for l in df_query("rh",trier_par=["salaire"])["lignes"]]
        self.assertEqual(vals,sorted(vals))
    def test_tri_desc(self):
        vals = [l["salaire"] for l in df_query("rh",trier_par=["salaire"],ordre_desc=True)["lignes"]]
        self.assertEqual(vals,sorted(vals,reverse=True))
    def test_sauvegarde(self):
        df_query("rh",filtre='service == "IT"',sauvegarder_sous="it")
        self.assertIn("it",_DATASETS); self.assertEqual(len(_DATASETS["it"]["df"]),2)
    def test_sans_filtre(self): self.assertEqual(df_query("rh")["nb_lignes"],6)
    def test_filtre_invalide(self): self.assertEqual(df_query("rh",filtre="$$$")["status"],"error")

# ── df_pivot ───────────────────────────────────────────────────────────────
class TestDfPivot(_Base):
    def test_basique(self):
        r = df_pivot("rh",index=["service"],valeurs=["salaire"],agregation="sum")
        self.assertEqual(r["status"],"success"); self.assertGreater(r["nb_lignes"],0)
    def test_totaux(self):
        r = df_pivot("rh",index=["service"],valeurs=["salaire"],totaux=True)
        self.assertIn("Total",[l["service"] for l in r["lignes"]])
    def test_toutes_agregations(self):
        for agg in ["sum","mean","count","min","max","median"]:
            self.assertEqual(df_pivot("rh",index=["service"],valeurs=["salaire"],agregation=agg)["status"],"success")
    def test_agregation_invalide(self):
        self.assertEqual(df_pivot("rh",index=["service"],agregation="variance")["status"],"error")
    def test_sauvegarde(self):
        df_pivot("rh",index=["service"],valeurs=["salaire"],sauvegarder_sous="piv")
        self.assertIn("piv",_DATASETS)

# ── df_merge ───────────────────────────────────────────────────────────────
class TestDfMerge(_Base):
    def setUp(self):
        super().setUp()
        _inject("grades",pd.DataFrame({"service":["RH","IT","Finance"],"niveau":["A","B","C"]}))
    def test_inner(self):
        r = df_merge("rh","grades",sur=["service"])
        self.assertEqual(r["status"],"success"); self.assertIn("niveau",r["colonnes"])
    def test_left(self):
        self.assertEqual(df_merge("rh","grades",sur=["service"],type_jointure="left")["nb_lignes"],6)
    def test_outer(self):
        self.assertEqual(df_merge("rh","grades",sur=["service"],type_jointure="outer")["status"],"success")
    def test_cles_differentes(self):
        _inject("info",pd.DataFrame({"dept":["RH","IT"],"chef":["Alice","Bob"]}))
        r = df_merge("rh","info",sur_gauche=["service"],sur_droite=["dept"])
        self.assertEqual(r["status"],"success"); self.assertIn("chef",r["colonnes"])
    def test_type_invalide(self):
        self.assertEqual(df_merge("rh","grades",sur=["service"],type_jointure="cross")["status"],"error")
    def test_sauvegarde(self):
        df_merge("rh","grades",sur=["service"],sauvegarder_sous="enr"); self.assertIn("enr",_DATASETS)

# ── df_concat ──────────────────────────────────────────────────────────────
class TestDfConcat(_Base):
    def setUp(self):
        super().setUp()
        _inject("rh2",pd.DataFrame({"nom":["N"],"service":["IT"],"salaire":[55000],"age":[30],
            "date_entree":pd.to_datetime(["2023-01-01"]),"date_naissance":pd.to_datetime(["1994-01-01"]),"note":[4.0]}))
    def test_outer(self):
        r = df_concat(["rh","rh2"],sauvegarder_sous="tous")
        self.assertEqual(r["status"],"success"); self.assertEqual(r["nb_lignes"],7)
    def test_colonne_source(self):
        r = df_concat(["rh","rh2"],sauvegarder_sous="src",ajouter_colonne_source=True)
        self.assertIn("_source",r["colonnes"])
    def test_inner_colonnes_communes(self):
        _inject("p",pd.DataFrame({"nom":["X"],"salaire":[50000]}))
        r = df_concat(["rh","p"],sauvegarder_sous="inn",jointure="inner")
        for col in r["colonnes"]: self.assertIn(col,["nom","salaire"])
    def test_moins_de_2(self):
        self.assertEqual(df_concat(["rh"],sauvegarder_sous="x")["status"],"error")
    def test_dataset_inexistant(self):
        self.assertEqual(df_concat(["rh","fantome"],sauvegarder_sous="x")["status"],"error")

# ── df_clean ───────────────────────────────────────────────────────────────
class TestDfClean(_Base):
    def setUp(self):
        super().setUp()
        df = _rh().copy()
        df.loc[0,"salaire"]=None; df.loc[1,"age"]=None
        df["nom"]=df["nom"].apply(lambda x: f"  {x}  " if isinstance(x,str) else x)
        _inject("sale",pd.concat([df,df.iloc[[0]]],ignore_index=True))
    def test_strip(self):
        df_clean("sale",strip_strings=True,sauvegarder_sous="p")
        for v in _DATASETS["p"]["df"]["nom"].dropna(): self.assertEqual(v,v.strip())
    def test_suppr_lignes_nan(self):
        r = df_clean("sale",nan_strategie="supprimer_lignes",sauvegarder_sous="ss")
        self.assertLess(r["nb_lignes_apres"],r["nb_lignes_avant"]); self.assertEqual(r["nb_nan_restants"],0)
    def test_imputer_moyenne(self):
        r = df_clean("sale",nan_strategie="imputer_moyenne",sauvegarder_sous="im")
        self.assertEqual(_DATASETS["im"]["df"]["salaire"].isna().sum(),0)
    def test_imputer_mediane(self): self.assertEqual(df_clean("sale",nan_strategie="imputer_mediane",sauvegarder_sous="x")["status"],"success")
    def test_imputer_mode(self):   self.assertEqual(df_clean("sale",nan_strategie="imputer_mode",sauvegarder_sous="x2")["status"],"success")
    def test_imputer_valeur(self): self.assertEqual(df_clean("sale",nan_strategie="imputer_valeur",nan_valeur="0",sauvegarder_sous="x3")["status"],"success")
    def test_imputer_valeur_sans_val(self): self.assertEqual(df_clean("sale",nan_strategie="imputer_valeur")["status"],"error")
    def test_dedup(self):
        r = df_clean("sale",deduplication=True,sauvegarder_sous="dd")
        self.assertLess(r["nb_lignes_apres"],r["nb_lignes_avant"])
    def test_suppr_cols(self):
        df_clean("rh",supprimer_colonnes=["note","age"],sauvegarder_sous="sc")
        for c in ["note","age"]: self.assertNotIn(c,_DATASETS["sc"]["df"].columns)
    def test_renommer_cols(self):
        df_clean("rh",renommer_colonnes={"nom":"prenom"},sauvegarder_sous="rc")
        self.assertIn("prenom",_DATASETS["rc"]["df"].columns)
    def test_strategie_invalide(self): self.assertEqual(df_clean("rh",nan_strategie="magie")["status"],"error")
    def test_save_par_defaut_ecrase(self):
        r = df_clean("rh",strip_strings=True); self.assertEqual(r["sauvegarde_sous"],"rh")

# ── df_cast ────────────────────────────────────────────────────────────────
class TestDfCast(_Base):
    def test_str_int(self):
        _inject("si",pd.DataFrame({"v":["1","2","3"]}))
        df_cast("si",{"v":"int"}); self.assertTrue(pd.api.types.is_integer_dtype(_DATASETS["si"]["df"]["v"]))
    def test_str_float(self):
        _inject("sf",pd.DataFrame({"v":["1.5","2.7"]}))
        self.assertEqual(df_cast("sf",{"v":"float"})["status"],"success")
    def test_str_datetime(self):
        _inject("dd",pd.DataFrame({"d":["2024-01-15","2024-06-30"]}))
        df_cast("dd",{"d":"datetime"}); self.assertTrue(pd.api.types.is_datetime64_any_dtype(_DATASETS["dd"]["df"]["d"]))
    def test_datetime_format(self):
        _inject("df2",pd.DataFrame({"d":["15/01/2024","30/06/2024"]}))
        self.assertEqual(df_cast("df2",{"d":{"type":"datetime","format":"%d/%m/%Y"}})["status"],"success")
    def test_category(self):
        df_cast("rh",{"service":"category"},sauvegarder_sous="cat")
        self.assertEqual(str(_DATASETS["cat"]["df"]["service"].dtype),"category")
    def test_bool(self):
        _inject("b",pd.DataFrame({"v":[1,0,1]})); self.assertEqual(df_cast("b",{"v":"bool"})["status"],"success")
    def test_col_inexistante(self): self.assertEqual(df_cast("rh",{"fantome":"int"})["status"],"error")
    def test_type_invalide(self):   self.assertEqual(df_cast("rh",{"age":"complex"})["status"],"error")
    def test_avertissement_nan(self):
        _inject("m",pd.DataFrame({"v":["1","deux","3"]}))
        r = df_cast("m",{"v":"int"}); self.assertGreater(len(r["avertissements"]),0)
    def test_sauvegarde(self):
        df_cast("rh",{"age":"str"},sauvegarder_sous="s"); self.assertIn("s",_DATASETS)

# ── df_apply ───────────────────────────────────────────────────────────────
class TestDfApply(_Base):
    def test_calcul_simple(self):
        r = df_apply("rh",["net = salaire * 0.75"]); self.assertIn("net",r["colonnes"])
    def test_concat_str(self):
        df_apply("rh",["lbl = nom + ' (' + service + ')'"]) 
        self.assertIn("Dupont (RH)",_DATASETS["rh"]["df"]["lbl"].tolist())
    def test_anciennete(self):
        df_apply("rh",["anc = (today - date_entree).dt.days / 365.25"])
        for v in _DATASETS["rh"]["df"]["anc"]: self.assertGreater(v,0)
    def test_age(self):
        df_apply("rh",["a = (today - date_naissance).dt.days // 365"])
        for v in _DATASETS["rh"]["df"]["a"]: self.assertGreater(v,20)
    def test_cut(self):
        r = df_apply("rh",['t = cut(age,bins=[0,30,40,50,100],labels=["<30","30-39","40-49","50+"])'])
        self.assertEqual(r["status"],"success")
    def test_plusieurs(self):
        r = df_apply("rh",["net=salaire*0.75","senior=age>40"]); self.assertEqual(len(r["colonnes_creees"]),2)
    def test_sans_egal(self):  self.assertEqual(df_apply("rh",["pas_egal"])["status"],"error")
    def test_col_inexistante(self): self.assertEqual(df_apply("rh",["x=fantome*2"])["status"],"error")
    def test_sauvegarde(self):
        df_apply("rh",["net=salaire*0.8"],sauvegarder_sous="rhn")
        self.assertIn("net",_DATASETS["rhn"]["df"].columns)

# ── df_rename ──────────────────────────────────────────────────────────────
class TestDfRename(_Base):
    def test_basique(self):
        r = df_rename("rh",{"nom":"prenom","age":"annees"})
        self.assertIn("prenom",r["colonnes"]); self.assertNotIn("nom",r["colonnes"])
    def test_col_inexistante(self): self.assertEqual(df_rename("rh",{"fantome":"new"})["status"],"error")
    def test_sauvegarde(self):
        df_rename("rh",{"nom":"prenom"},sauvegarder_sous="ren")
        self.assertIn("prenom",_DATASETS["ren"]["df"].columns)
    def test_ecrase_par_defaut(self):
        df_rename("rh",{"nom":"prenom"}); self.assertIn("prenom",_DATASETS["rh"]["df"].columns)

# ── df_sample ──────────────────────────────────────────────────────────────
class TestDfSample(_Base):
    def test_n(self):
        r = df_sample("rh",n=3,graine=42); self.assertEqual(r["nb_lignes_sample"],3)
    def test_fraction(self):
        r = df_sample("rh",fraction=0.5,graine=42); self.assertEqual(r["nb_lignes_sample"],3)
    def test_reproductible(self):
        r1 = df_sample("rh",n=3,graine=42,sauvegarder_sous="s1")
        r2 = df_sample("rh",n=3,graine=42,sauvegarder_sous="s2")
        self.assertEqual([l["nom"] for l in r1["lignes"]],[l["nom"] for l in r2["lignes"]])
    def test_stratifie(self):
        self.assertEqual(df_sample("rh",fraction=0.5,stratifier_par="service",graine=42)["status"],"success")
    def test_n_et_fraction(self):   self.assertEqual(df_sample("rh",n=2,fraction=0.5)["status"],"error")
    def test_rien(self):            self.assertEqual(df_sample("rh")["status"],"error")
    def test_fraction_invalide(self): self.assertEqual(df_sample("rh",fraction=1.5)["status"],"error")

# ── df_anonymize ───────────────────────────────────────────────────────────
class TestDfAnonymize(_Base):
    def _anon(self): return _DATASETS.get("rh_anon",{}).get("df")
    def test_supprimer(self):
        df_anonymize("rh",{"nom":"supprimer"}); self.assertNotIn("nom",self._anon().columns)
    def test_hacher_prefixe(self):
        df_anonymize("rh",{"nom":"hacher"},sel="s")
        for v in self._anon()["nom"].dropna(): self.assertTrue(str(v).startswith("H_"))
    def test_hacher_reproductible(self):
        df_anonymize("rh",{"nom":"hacher"},sel="f",sauvegarder_sous="a1")
        df_anonymize("rh",{"nom":"hacher"},sel="f",sauvegarder_sous="a2")
        self.assertEqual(_DATASETS["a1"]["df"]["nom"].tolist(),_DATASETS["a2"]["df"]["nom"].tolist())
    def test_pseudonymiser(self):
        df_anonymize("rh",{"nom":"pseudonymiser"},sel="s")
        for v in self._anon()["nom"].dropna(): self.assertTrue(str(v).startswith("P_"))
    def test_masquer(self):
        df_anonymize("rh",{"nom":"masquer"})
        for v in self._anon()["nom"].dropna(): self.assertEqual(v,"***")
    def test_generaliser_date_annee(self):
        df_anonymize("rh",{"date_naissance":{"op":"generaliser_date","precision":"annee"}})
        for v in self._anon()["date_naissance"].dropna(): self.assertGreater(int(v),1900)
    def test_generaliser_date_mois(self):
        self.assertEqual(df_anonymize("rh",{"date_naissance":{"op":"generaliser_date","precision":"mois"}})["status"],"success")
    def test_generaliser_nombre(self):
        df_anonymize("rh",{"salaire":{"op":"generaliser_nombre","arrondi":5000}})
        for v in self._anon()["salaire"].dropna(): self.assertEqual(v%5000,0.0)
    def test_bruit_gaussien(self):
        df_anonymize("rh",{"salaire":{"op":"bruit_gaussien","ecart_type":0.05}})
        self.assertFalse((_DATASETS["rh"]["df"]["salaire"].values==self._anon()["salaire"].values).all())
    def test_sans_sel(self):
        r = df_anonymize("rh",{"nom":"hacher"}); self.assertGreater(len(r["avertissements"]),0)
    def test_op_invalide(self):
        self.assertEqual(df_anonymize("rh",{"nom":"tokeniser"})["status"],"error")
    def test_col_inexistante(self):
        self.assertEqual(df_anonymize("rh",{"fantome":"supprimer"})["status"],"error")
    def test_sauvegarder_sous(self):
        df_anonymize("rh",{"nom":"masquer"},sauvegarder_sous="rgpd")
        self.assertIn("rgpd",_DATASETS); self.assertNotIn("rh_anon",_DATASETS)
    def test_multi_ops(self):
        r = df_anonymize("rh",{"nom":"pseudonymiser","salaire":{"op":"generaliser_nombre","arrondi":1000},"date_naissance":{"op":"generaliser_date","precision":"annee"}},sel="t")
        self.assertEqual(len(r["operations"]),3)

# ── df_write ───────────────────────────────────────────────────────────────
class TestDfWrite(_Base):
    def setUp(self):
        super().setUp(); self.tmp = tempfile.mkdtemp()
    def test_csv(self):
        dest = os.path.join(self.tmp,"out.csv"); df_write("rh",destination=dest,format="csv")
        self.assertEqual(len(pd.read_csv(dest)),6)
    def test_excel(self):
        dest = os.path.join(self.tmp,"out.xlsx"); df_write("rh",destination=dest,format="excel")
        self.assertEqual(len(pd.read_excel(dest)),6)
    def test_multi_feuilles(self):
        _inject("rh2",_rh()); dest = os.path.join(self.tmp,"m.xlsx")
        df_write("rh",destination=dest,format="excel",datasets_supplementaires=["rh2"])
        self.assertIn("rh2",pd.ExcelFile(dest).sheet_names)
    def test_separateur(self):
        dest = os.path.join(self.tmp,"s.csv"); df_write("rh",destination=dest,separateur=";")
        self.assertIn(";",Path(dest).read_text(encoding="utf-8-sig"))
    def test_retour_champs(self):
        dest = os.path.join(self.tmp,"o2.csv"); r = df_write("rh",destination=dest)
        for k in ["fichier","nb_lignes","taille"]: self.assertIn(k,r)
    def test_format_inconnu(self):
        self.assertEqual(df_write("rh",destination=os.path.join(self.tmp,"o.parquet"),format="parquet")["status"],"error")

# ── df_drop ────────────────────────────────────────────────────────────────
class TestDfDrop(_Base):
    def test_simple(self):
        r = df_drop(["rh"]); self.assertIn("rh",r["supprimes"]); self.assertNotIn("rh",_DATASETS)
    def test_multiple(self):
        _inject("b",pd.DataFrame({"x":[1]}))
        self.assertEqual(len(df_drop(["rh","b"])["supprimes"]),2)
    def test_introuvable(self):
        r = df_drop(["fantome"]); self.assertIn("fantome",r["introuvables"])
    def test_mixte(self):
        r = df_drop(["rh","fantome"])
        self.assertIn("rh",r["supprimes"]); self.assertIn("fantome",r["introuvables"])

# ── JSON-sérialisabilité ───────────────────────────────────────────────────
class TestJsonSerializable(_Base):
    def _chk(self, obj):
        import json
        try: json.dumps(obj)
        except (TypeError,ValueError) as e: self.fail(f"Non sérialisable: {e!r}")
    def test_info(self):    self._chk(df_info("rh"))
    def test_groupby(self): self._chk(df_groupby("rh",["service"],{"salaire":["sum","mean"]}))
    def test_correlate(self): self._chk(df_correlate("rh"))
    def test_apply_dates(self): self._chk(df_apply("rh",["anc=(today-date_entree).dt.days/365.25"]))
    def test_anonymize(self): self._chk(df_anonymize("rh",{"nom":"hacher"},sel="t"))
    def test_outliers(self):
        df = _rh().copy()
        df.loc[len(df)]=["X","RH",999999,35,pd.Timestamp("2020-01-01"),pd.Timestamp("1988-01-01"),4.0]
        _inject("big",df); self._chk(df_outliers("big"))

if __name__ == "__main__":
    unittest.main(verbosity=2)
