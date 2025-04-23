import re
from pathlib import Path
from datetime import datetime

HOME       = Path.home()
DOWNLOADS  = HOME / "Downloads"
RIS_FILE   = DOWNLOADS / "seuarquivo.ris"

# ------------------ AST e DNF ------------------

class Expr:
    def eval(self, txt: str) -> bool:
        raise NotImplementedError

class Term(Expr):
    def __init__(self, term: str):
        self.term = term.lower().strip()
    def eval(self, txt: str) -> bool:
        return self.term in txt.lower()
    def __repr__(self):
        return f'"{self.term}"'

class NotOp(Expr):
    def __init__(self, child: Expr):
        self.child = child
    def eval(self, txt: str) -> bool:
        return not self.child.eval(txt)
    def __repr__(self):
        return f'NOT({self.child})'

class BinOp(Expr):
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

class AndOp(BinOp):
    def eval(self, txt: str) -> bool:
        return self.left.eval(txt) and self.right.eval(txt)
    def __repr__(self):
        return f'({self.left} AND {self.right})'

class OrOp(BinOp):
    def eval(self, txt: str) -> bool:
        return self.left.eval(txt) or self.right.eval(txt)
    def __repr__(self):
        return f'({self.left} OR {self.right})'

def tokenize(q: str):
    # Captura parênteses, operadores e termos (mesmo multi-palavra)
    tokens = re.findall(
        r'\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^()\s]+(?:\s+[^()\s]+)*',
        q, flags=re.IGNORECASE
    )
    return [t.strip() for t in tokens if t.strip()]

def shunting_yard(tokens):
    # Precedência: NOT > AND > OR
    prec = {'NOT':3,'AND':2,'OR':1}
    output, stack = [], []
    for tk in tokens:
        up = tk.upper()
        if up in prec:
            # operadores binários e unários
            while stack and stack[-1] != '(' and prec.get(stack[-1],0) >= prec[up]:
                output.append(stack.pop())
            stack.append(up)
        elif tk == '(':
            stack.append(tk)
        elif tk == ')':
            while stack and stack[-1] != '(':
                output.append(stack.pop())
            stack.pop()  # descarta '('
        else:
            output.append(tk)
    # esvazia pilha (descarta parênteses remanescentes)
    while stack:
        op = stack.pop()
        if op not in ('(',')'):
            output.append(op)
    return output

def build_ast(rpn):
    stack = []
    for tk in rpn:
        up = tk.upper()
        if up == 'NOT':
            child = stack.pop()
            stack.append(NotOp(child))
        elif up == 'AND':
            right = stack.pop(); left = stack.pop()
            stack.append(AndOp(left, right))
        elif up == 'OR':
            right = stack.pop(); left = stack.pop()
            stack.append(OrOp(left, right))
        else:
            stack.append(Term(tk))
    return stack[0]

def parse_query(q: str) -> Expr:
    tokens = tokenize(q)
    rpn = shunting_yard(tokens)
    return build_ast(rpn)

def ast_to_dnf(expr: Expr):
    """ Converte o AST para Disjunctive Normal Form (lista de conjunções). """
    if isinstance(expr, Term) or isinstance(expr, NotOp):
        return [[expr]]
    if isinstance(expr, OrOp):
        return ast_to_dnf(expr.left) + ast_to_dnf(expr.right)
    if isinstance(expr, AndOp):
        left_clauses  = ast_to_dnf(expr.left)
        right_clauses = ast_to_dnf(expr.right)
        # produto cartesiano: todas combinações de cláusulas
        return [l + r for l in left_clauses for r in right_clauses]
    return []

# ------------------ Parsing do RIS ------------------

def parse_ris_entries(path: Path):
    entries, current = [], []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for ln in f:
            current.append(ln.rstrip('\n'))
            if ln.startswith('ER  -'):
                entries.append(current)
                current = []
    if current:
        entries.append(current)
    return entries

def extract_tag(entry, tag):
    prefix = tag + '  -'
    return [ln[len(prefix):].strip() for ln in entry if ln.startswith(prefix)]

def clean_id(raw: str) -> str:
    # isola apenas doi.org/... ou 10.xxxx/...
    m = re.search(r'(doi\.org/\S+)', raw, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'(10\.\d{4,9}/[^\s]+)', raw)
    if m:
        return m.group(1)
    return raw.strip()

# ------------------ Loop Principal ------------------

def main():
    if not RIS_FILE.exists():
        print(f"RIS não encontrado: {RIS_FILE}")
        return

    entries = parse_ris_entries(RIS_FILE)
    print(f"Total de entradas no RIS: {len(entries)}")

    while True:
        query = input("\nQuery (ou SAIR para encerrar): ").strip()
        if query.upper() == 'SAIR':
            print("Fim.")
            break

        expr = parse_query(query)
        dnf = ast_to_dnf(expr)
        print(f"\nDNF gerou {len(dnf)} conjunções:")
        # 1) listar e contar cada conjunção
        for i, conj in enumerate(dnf, start=1):
            count = 0
            for ent in entries:
                ti  = extract_tag(ent, 'TI')
                ab  = extract_tag(ent, 'AB')
                kws = extract_tag(ent, 'KW')
                texto = ' '.join(ti + ab + kws)
                if all(c.eval(texto) for c in conj):
                    count += 1
            expr_str = ' AND '.join(repr(c) for c in conj)
            print(f"  {i}. {expr_str}  → {count} itens")

        # 2) coleta resultados de qualquer conjunção satisfeita
        results = []
        for ent in entries:
            ti  = extract_tag(ent, 'TI')
            ab  = extract_tag(ent, 'AB')
            kws = extract_tag(ent, 'KW')
            texto = ' '.join(ti + ab + kws)
            if any(all(c.eval(texto) for c in conj) for conj in dnf):
                raw = (extract_tag(ent, 'DO') or extract_tag(ent, 'UR') or [''])[0]
                cid = clean_id(raw)
                if cid:
                    results.append(cid)

        if not results:
            print("Nenhum item encontrado para essa query.")
            continue

        # salva em ~/Downloads
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe = re.sub(r'[^\w\-]', '_', query)[:30]
        out_file = DOWNLOADS / f"resultado_{safe}_{ts}.txt"
        with out_file.open('w', encoding='utf-8') as f:
            f.write(', '.join(results))

        print(f"\nTotal geral de IDs: {len(results)}")
        print(f"Gravado em: {out_file}")

if __name__ == '__main__':
    main()