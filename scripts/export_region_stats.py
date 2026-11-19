"""Export VM_ASD (private) region sums to region-stats.json for the public page.

Only aggregates per region are written: VM_ASD itself stays private, and no
credential ends up in the repo. Uses the portal sign-in of ArcGIS Pro.

Run (ArcGIS Pro signed in to https://geoportail.anss.gov.ma/portal):
    "C:\\Users\\PC\\AppData\\Local\\ESRI\\conda\\envs\\arcgispro-py3-rapport\\python.exe" scripts\\export_region_stats.py
Then commit and push region-stats.json.
"""
import datetime
import json
from pathlib import Path

from arcgis.features import Table
from arcgis.gis import GIS

TABLE_URL = "https://geoportail.anss.gov.ma/server/rest/services/Hosted/VM_ASD/FeatureServer/0"
# Commune rows only, so province/region total rows (if ever added) are not counted twice.
WHERE = "type_ = 'Indicateur Commune'"
# Key read by index.html -> VM_ASD field summed.
FIELDS = {
    "eligible": "nombre_dossiers_eligibles",
    "households": "nb_total_beneficiaires_demandeurs_asd",  # not "menages": that is the census total
    "children": "nombre_total_enfants",
    "population": "individus",
    "widows": "cm_veuves",
}
OUTPUT = Path(__file__).resolve().parent.parent / "region-stats.json"


def main():
    gis = GIS("pro")
    if "geoportail.anss.gov.ma" not in gis.url:
        raise SystemExit(f"ArcGIS Pro est connecté à {gis.url} : rendez actif https://geoportail.anss.gov.ma/portal (Projet > Portails) et connectez-vous.")
    table = Table(TABLE_URL, gis)

    latest = table.query(
        where=WHERE,
        out_fields="annee,mois",
        order_by_fields="annee DESC, mois DESC",
        result_record_count=1,
        return_geometry=False,
    ).features
    if not latest or latest[0].attributes.get("annee") is None or latest[0].attributes.get("mois") is None:
        raise SystemExit("VM_ASD : aucune période (annee/mois) trouvée.")
    annee, mois = int(latest[0].attributes["annee"]), int(latest[0].attributes["mois"])

    result = table.query(
        where=f"({WHERE}) AND annee = {annee} AND mois = {mois}",
        group_by_fields_for_statistics="code_region_hcp,nom_region",
        out_statistics=[
            {"statisticType": "sum", "onStatisticField": field, "outStatisticFieldName": key}
            for key, field in FIELDS.items()
        ],
        return_geometry=False,
    )
    # Some servers return statistic names in another case: look them up case-insensitively.
    rows = []
    for feature in result.features:
        attrs = {name.lower(): value for name, value in feature.attributes.items()}
        rows.append({
            "code_region_hcp": attrs.get("code_region_hcp"),
            "nom_region": attrs.get("nom_region"),
            **{key: attrs.get(key) for key in FIELDS},
        })
    if not rows:
        raise SystemExit(f"VM_ASD : aucune ligne pour {mois}/{annee}.")

    OUTPUT.write_text(json.dumps({
        "source": "VM_ASD",
        "annee": annee,
        "mois": mois,
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "rows": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{OUTPUT.name} : {len(rows)} lignes pour {mois:02d}/{annee}.")


if __name__ == "__main__":
    main()
