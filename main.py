import re
import time
from pathlib import Path
from datetime import datetime

# --------------------------------------------------
# CONFIGURAÇÃO DE CAMINHOS
# --------------------------------------------------
HOME = Path.home()
DOWNLOADS = HOME / "Downloads"

# nome do seu arquivo RIS dentro de ~/Downloads
RIS_FILENAME = "Zotero.ris"
RIS_PATH = DOWNLOADS / RIS_FILENAME

# --------------------------------------------------
# FUNÇÕES AUXILIARES
# --------------------------------------------------
def parse_ris_entries(ris_path: Path):
    entries, current = [], []
    with ris_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            current.append(line.rstrip("\n"))
            if line.startswith("ER  -"):
                entries.append(current)
                current = []
    if current:
        entries.append(current)
    return entries

def extract_tag_values(entry_lines, tag):
    prefix = tag + "  -"
    return [
        line[len(prefix):].strip()
        for line in entry_lines
        if line.startswith(prefix)
    ]

def extract_first_tag(entry_lines, tag):
    vals = extract_tag_values(entry_lines, tag)
    return vals[0] if vals else None

def clean_identifier(raw: str) -> str:
    raw = raw.strip()
    m = re.search(r"(doi\.org/\S+)", raw, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"(10\.\d{4,9}/[^\s]+)", raw)
    if m:
        return m.group(1)
    if raw.startswith("10."):
        return raw
    return raw

def matches_query(text: str, terms: list[str], op: str) -> bool:
    txt = text.lower()
    if op == "AND":
        return all(t.lower() in txt for t in terms)
    if op == "OR":
        return any(t.lower() in txt for t in terms)
    if op == "NOT":
        return terms[0].lower() not in txt
    return terms[0].lower() in txt  # SINGLE

def parse_user_query(query: str):
    q = query.strip()
    if " AND " in q.upper():
        return [p.strip() for p in re.split(r"(?i)\s+AND\s+", q)], "AND"
    if " OR " in q.upper():
        return [p.strip() for p in re.split(r"(?i)\s+OR\s+", q)], "OR"
    if q.upper().startswith("NOT "):
        return [q[4:].strip()], "NOT"
    return [q], "SINGLE"

# --------------------------------------------------
# FLUXO PRINCIPAL EM LOOP
# --------------------------------------------------
def main():
    if not RIS_PATH.exists():
        print(f"Arquivo RIS não encontrado: {RIS_PATH}")
        return

    # Carrega e divide as entradas
    entries = parse_ris_entries(RIS_PATH)
    total_entries = len(entries)
    print(f"Total de entradas no arquivo: {total_entries}")

    while True:
        query = input(
            "\nDigite sua busca "
            "(e.g. 'lixo eletrônico', 'patrimônio ambiental AND sustentabilidade', "
            "'NOT e-waste') ou SAIR para encerrar: "
        ).strip()
        if query.upper() == "SAIR":
            print("Encerrando o programa.")
            break

        terms, op = parse_user_query(query)
        print(f"Buscando {terms} ({op}) em TI, AB e KW...")

        found = []
        for entry in entries:
            ti = extract_first_tag(entry, "TI") or ""
            ab = extract_first_tag(entry, "AB") or ""
            kws = extract_tag_values(entry, "KW")
            texto = " ".join([ti, ab] + kws)

            if matches_query(texto, terms, op):
                raw = extract_first_tag(entry, "DO") or extract_first_tag(entry, "UR") or ""
                cleaned = clean_identifier(raw)
                if cleaned:
                    found.append(cleaned)

        if not found:
            print("Nenhum resultado encontrado para essa busca.")
            continue

        # cria nome de arquivo único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r"[^\w\-]", "_", query)[:30]
        filename = f"resultado_{safe_query}_{timestamp}.txt"
        output_path = DOWNLOADS / filename

        # salva sem sobrescrever
        with output_path.open("w", encoding="utf-8") as out:
            out.write(", ".join(found))

        print(f"{len(found)} resultados gravados em: {output_path}")

if __name__ == "__main__":
    main()