import re
from pathlib import Path
from datetime import datetime

HOME       = Path.home()
DOWNLOADS  = HOME / "Downloads"
RIS_FILE   = DOWNLOADS / "Zotero.ris"

# ------------------ AST e DNF ------------------

class Expr:
    def eval(self, txt: str) -> bool:
        raise NotImplementedError

class Term(Expr):
    def __init__(self, term: str):
        self.term = term.lower().strip()
    def eval(self, txt: str) -> bool:
        return self.term in txt.lower()

class NotOp(Expr):
    def __init__(self, child: Expr):
        self.child = child
    def eval(self, txt: str) -> bool:
        return not self.child.eval(txt)

class BinOp(Expr):
    def __init__(self, left: Expr, right: Expr):
        self.left = left; self.right = right

class AndOp(BinOp):
    def eval(self, txt: str) -> bool:
        return self.left.eval(txt) and self.right.eval(txt)

class OrOp(BinOp):
    def eval(self, txt: str) -> bool:
        return self.left.eval(txt) or self.right.eval(txt)

def tokenize(q: str):
    return [t.strip() for t in
            re.findall(r'\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^()\s]+(?:\s+[^()\s]+)*',
                       q, flags=re.IGNORECASE) if t.strip()]

def shunting_yard(tokens):
    prec = {'NOT':3,'AND':2,'OR':1}
    out, stack = [], []
    for tk in tokens:
        u = tk.upper()
        if u in prec:
            while stack and stack[-1] != '(' and (
                prec.get(stack[-1],0) > prec[u] or
                (prec.get(stack[-1],0) == prec[u] and u!='NOT')
            ):
                out.append(stack.pop())
            stack.append(u)
        elif tk == '(':
            stack.append(tk)
        elif tk == ')':
            while stack and stack[-1] != '(':
                out.append(stack.pop())
            stack.pop()
        else:
            out.append(tk)
    out += reversed(stack)
    return out

def build_ast(rpn):
    stack = []
    for tk in rpn:
        u = tk.upper()
        if u == 'NOT':
            c = stack.pop(); stack.append(NotOp(c))
        elif u == 'AND':
            r = stack.pop(); l = stack.pop(); stack.append(AndOp(l,r))
        elif u == 'OR':
            r = stack.pop(); l = stack.pop(); stack.append(OrOp(l,r))
        else:
            stack.append(Term(tk))
    return stack[0]

def parse_query(q: str) -> Expr:
    return build_ast(shunting_yard(tokenize(q)))

def ast_to_dnf(expr: Expr):
    """Converte AST em lista de conjunções (DNF)."""
    if isinstance(expr, Term) or isinstance(expr, NotOp):
        return [[expr]]
    if isinstance(expr, OrOp):
        return ast_to_dnf(expr.left) + ast_to_dnf(expr.right)
    if isinstance(expr, AndOp):
        d1 = ast_to_dnf(expr.left); d2 = ast_to_dnf(expr.right)
        return [c1 + c2 for c1 in d1 for c2 in d2]
    return []

# ------------------ Parsing RIS ------------------

def parse_ris_entries(path: Path):
    entries, cur = [], []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for ln in f:
            cur.append(ln.rstrip('\n'))
            if ln.startswith('ER  -'):
                entries.append(cur); cur = []
    if cur: entries.append(cur)
    return entries

def extract_tag(entry, tag):
    p = tag + '  -'
    return [ln[len(p):].strip() for ln in entry if ln.startswith(p)]

def clean_id(raw: str) -> str:
    m = re.search(r'(doi\.org/\S+)', raw, re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r'(10\.\d{4,9}/[^\s]+)', raw)
    if m: return m.group(1)
    return raw.strip()

# ------------------ Main Loop ------------------

def main():
    if not RIS_FILE.exists():
        print(f"RIS não encontrado: {RIS_FILE}")
        return

    entries = parse_ris_entries(RIS_FILE)
    print(f"Total de entradas no RIS: {len(entries)}")

    while True:
        q = input("\nQuery (ou SAIR): ").strip()
        if q.upper() == 'SAIR':
            break

        expr = parse_query(q)
        dnf = ast_to_dnf(expr)
        print(f"Expandindo para {len(dnf)} conjunções na DNF.")

        results = []
        for ent in entries:
            ti  = extract_tag(ent,'TI')
            ab  = extract_tag(ent,'AB')
            kws = extract_tag(ent,'KW')
            txt = ' '.join(ti+ab+kws)

            # testar cada conjunção
            if any(all(c.eval(txt) for c in conj) for conj in dnf):
                raw = (extract_tag(ent,'DO') or extract_tag(ent,'UR') or [''])[0]
                cid = clean_id(raw)
                if cid:
                    results.append(cid)

        if not results:
            print("Nenhum item encontrado.")
            continue

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        fn = re.sub(r'[^\w\-]','_',q)[:30]
        out = DOWNLOADS / f"resultado_{fn}_{ts}.txt"
        with out.open('w', encoding='utf-8') as f:
            f.write(', '.join(results))

        print(f"{len(results)} IDs em {out}")

if __name__=='__main__':
    main()