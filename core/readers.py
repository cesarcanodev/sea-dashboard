"""Lecture de fichiers sources (CSV / Excel / PDF) vers un DataFrame brut.

Chaque lecteur renvoie un DataFrame *non normalisé* : les colonnes gardent
leurs en-têtes d'origine. La normalisation est faite séparément par
``core.normalizer``.
"""

from __future__ import annotations

import csv
import io
import os

import pandas as pd


class ReaderError(Exception):
    """Erreur claire et lisible lors de la lecture d'un fichier source."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_name(file) -> str:
    """Récupère un nom de fichier, qu'on reçoive un chemin (str) ou un
    file-like (uploader Streamlit qui expose ``.name``)."""
    if isinstance(file, (str, os.PathLike)):
        return str(file)
    name = getattr(file, "name", None)
    if not name:
        raise ReaderError(
            "Impossible de déterminer le nom du fichier : aucune extension détectable."
        )
    return name


def _read_bytes(file) -> bytes:
    """Renvoie le contenu binaire d'un fichier, qu'il s'agisse d'un chemin
    ou d'un objet file-like."""
    if isinstance(file, (str, os.PathLike)):
        with open(file, "rb") as fh:
            return fh.read()
    data = file.read()
    # Permet de relire le même uploader plusieurs fois.
    try:
        file.seek(0)
    except Exception:
        pass
    return data


# --------------------------------------------------------------------------- #
# Lecteurs par format
# --------------------------------------------------------------------------- #
def read_csv(file) -> pd.DataFrame:
    """Lit un CSV en détectant automatiquement le séparateur (`,` ou `;`)."""
    raw = _read_bytes(file)
    text = _decode(raw)

    sep = _sniff_separator(text)
    try:
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    except Exception as exc:  # pragma: no cover - garde-fou
        raise ReaderError(f"CSV illisible : {exc}") from exc

    if df.empty or df.shape[1] == 0:
        raise ReaderError("Le CSV ne contient aucune donnée exploitable.")
    return df


def read_excel(file) -> pd.DataFrame:
    """Lit la première feuille d'un classeur Excel via openpyxl."""
    raw = _read_bytes(file)
    try:
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", dtype=str)
    except Exception as exc:
        raise ReaderError(f"Fichier Excel illisible : {exc}") from exc

    if df.empty or df.shape[1] == 0:
        raise ReaderError("Le fichier Excel ne contient aucune donnée exploitable.")
    return df


def read_pdf(file) -> pd.DataFrame:
    """Extrait les tableaux d'un PDF via pdfplumber.

    Concatène tous les tableaux trouvés dans toutes les pages. Lève une
    ``ReaderError`` claire si aucun tableau n'est détecté.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise ReaderError(
            "pdfplumber n'est pas installé : impossible de lire les PDF."
        ) from exc

    raw = _read_bytes(file)
    tables: list[pd.DataFrame] = []

    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table or len(table) < 2:
                        continue
                    header, *rows = table
                    header = [
                        (h or f"col_{i}").strip() for i, h in enumerate(header)
                    ]
                    df = pd.DataFrame(rows, columns=header)
                    tables.append(df)
    except Exception as exc:
        raise ReaderError(f"PDF illisible : {exc}") from exc

    if not tables:
        raise ReaderError(
            "Aucun tableau n'a été trouvé dans le PDF. "
            "Vérifiez que le document contient bien des données tabulaires."
        )

    # Aligne sur l'union des colonnes pour concaténer proprement.
    return pd.concat(tables, ignore_index=True)


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #
def read_file(file) -> pd.DataFrame:
    """Détecte le format par l'extension et délègue au bon lecteur."""
    name = _get_name(file).lower()
    ext = os.path.splitext(name)[1]

    if ext == ".csv":
        df = read_csv(file)
    elif ext in (".xlsx", ".xls"):
        df = read_excel(file)
    elif ext == ".pdf":
        df = read_pdf(file)
    else:
        raise ReaderError(
            f"Format de fichier non supporté : « {ext or '(aucune extension)'} ». "
            "Formats acceptés : .csv, .xlsx, .xls, .pdf"
        )

    # Détecte la vraie ligne d'en-tête (exports avec lignes de titre au-dessus).
    from core.normalizer import promote_header
    return promote_header(df)


# --------------------------------------------------------------------------- #
# Détails d'implémentation
# --------------------------------------------------------------------------- #
def _decode(raw: bytes) -> str:
    """Décode des octets en texte, en essayant quelques encodages courants."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Dernier recours : on remplace les octets invalides.
    return raw.decode("utf-8", errors="replace")


def _sniff_separator(text: str) -> str:
    """Devine le séparateur d'un CSV entre `,` et `;`."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        if dialect.delimiter in (",", ";", "\t"):
            return dialect.delimiter
    except csv.Error:
        pass

    # Heuristique de secours : on compte sur la première ligne.
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    if first_line.count(";") > first_line.count(","):
        return ";"
    return ","
