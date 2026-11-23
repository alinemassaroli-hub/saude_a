"""Validação estrutural de lotes Saúde A. Python 3.12; sem dependências externas."""
import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
MAX_QUESTOES = 100
SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def contar_palavras(texto):
    return sum(any(c.isalnum() for c in token) for token in texto.split())


def carregar_json(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Arquivo excede 2 MB.')

    def objeto(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Chave JSON repetida: {key}')
            result[key] = value
        return result

    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=objeto,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Número JSON inválido: ' + s)))


def catalogo():
    rows = json.loads((ROOT / 'references/taxonomia.json').read_text(encoding='utf-8'))['subcategorias']
    return {r['subcategoria_codigo']: r for r in rows}


def validar(payload):
    errors, report = [], []
    if not isinstance(payload, dict):
        return ['O lote deve ser um objeto JSON.'], report
    if type(payload.get('schema_version')) is not int or payload['schema_version'] != 1:
        errors.append('schema_version deve ser 1.')
    for key in ('lote_id', 'autor', 'origem', 'data_criacao'):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            errors.append(f'{key} ausente ou inválido.')
    if not SLUG.fullmatch(str(payload.get('lote_id', ''))):
        errors.append('lote_id: use letras, números, ponto, hífen ou sublinhado, até 160 caracteres.')
    try:
        created = datetime.fromisoformat(str(payload.get('data_criacao', '')).replace('Z', '+00:00'))
        if created.tzinfo is None:
            raise ValueError('fuso ausente')
    except ValueError:
        errors.append('data_criacao deve ser data/hora ISO 8601 com fuso.')
    questions = payload.get('questoes')
    if not isinstance(questions, list) or not 1 <= len(questions) <= MAX_QUESTOES:
        errors.append('questoes deve conter de 1 a 100 objetos.')
        return errors, report
    taxonomy, ids = catalogo(), set()
    for index, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            errors.append(f'Questão {index}: deve ser um objeto.'); continue
        label = str(q.get('id', index))

        def error(message):
            errors.append(f'{label}: {message}')

        def identifier(value):
            if not isinstance(value, str) or not SLUG.fullmatch(value):
                error('ID ausente ou inválido.'); return False
            if value in ids:
                error('ID duplicado no lote: ' + value); return False
            ids.add(value)
            return True

        identifier(q.get('id'))
        for key in ('enunciado', 'explicacao', 'dica_professor', 'tema', 'objetivo',
                    'dificuldade', 'justificativa', 'profissao', 'publico', 'status_editorial', 'data_validacao'):
            if not isinstance(q.get(key), str) or not q[key].strip():
                error(key + ' ausente ou inválido.')
        if q.get('profissao') != 'Enfermagem':
            error('A taxonomia disponível corresponde a Enfermagem.')
        if str(q.get('dificuldade', '')).casefold() not in ('fácil', 'moderada', 'difícil'):
            error('dificuldade deve ser Fácil, Moderada ou Difícil (estimativa editorial).')
        try:
            date.fromisoformat(str(q.get('data_validacao', '')))
        except ValueError:
            error('data_validacao deve ser AAAA-MM-DD.')
        base = q.get('versao_base')
        if base is not None and (type(base) is not int or base < 0):
            error('versao_base deve ser inteiro não negativo.')
        row = taxonomy.get(str(q.get('subcategoria_codigo')))
        if row is None or any(q.get(k) != row[k] for k in
                              ('categoria_codigo', 'categoria', 'subcategoria_codigo', 'subcategoria')):
            error('Códigos e nomes não correspondem à taxonomia aprovada.')
        explanation = q.get('explicacao') if isinstance(q.get('explicacao'), str) else ''
        count = contar_palavras(explanation)
        report.append({'id': label, 'palavras_explicacao': count})
        if not 750 <= count <= 1000:
            error(f'explicação com {count} palavras; esperado 750–1000.')
        options = q.get('alternativas')
        if not isinstance(options, list):
            options = []
        if len(options) != 5:
            error('São necessárias exatamente cinco alternativas.')
        mapping, texts = {}, set()
        for option in options:
            if not isinstance(option, dict):
                error('Alternativa deve ser objeto.'); continue
            oid, text = option.get('id'), option.get('texto')
            valid_id = identifier(oid)
            if not isinstance(text, str) or not text.strip():
                error('Texto de alternativa ausente.'); continue
            normalized = text.strip().casefold()
            if normalized in texts:
                error('Textos de alternativas duplicados.')
            texts.add(normalized)
            if re.search(r'\b(todas|nenhuma) (as |das )?anteriores\b', normalized):
                error('Alternativa depende da posição de apresentação.')
            if valid_id:
                mapping[oid] = text
                if oid in explanation:
                    error('Explicação menciona ID de alternativa.')
        answer = q.get('gabarito')
        if not isinstance(answer, list):
            answer = []
        kind = q.get('tipo_resposta')
        if kind not in ('unica', 'multipla'):
            error('tipo_resposta deve ser unica ou multipla.')
        if kind == 'unica' and len(answer) != 1:
            error('Resposta única exige um gabarito.')
        if kind == 'multipla':
            if not 2 <= len(answer) <= 4:
                error('Seleção múltipla exige de duas a quatro corretas.')
            if 'selecione todas as alternativas corretas' not in str(q.get('enunciado', '')).casefold():
                error('Seleção múltipla exige comando explícito.')
            for key in ('justificativa_multipla', 'regra_pontuacao'):
                if not isinstance(q.get(key), str) or not q[key].strip():
                    error(key + ' obrigatório para seleção múltipla.')
        seen = set()
        for item in answer:
            if not isinstance(item, dict):
                error('Gabarito deve conter objetos.'); continue
            oid = item.get('id')
            if not isinstance(oid, str) or oid not in mapping:
                error('Gabarito aponta ID inexistente.'); continue
            if oid in seen:
                error('ID repetido no gabarito.')
            seen.add(oid)
            if item.get('texto') != mapping[oid]:
                error('Texto do gabarito diverge da alternativa.')
        refs = q.get('referencias')
        if not isinstance(refs, list) or not refs:
            error('referencias deve ser lista não vazia.'); refs = []
        for ref in refs:
            if not isinstance(ref, dict):
                error('Referência deve ser objeto.'); continue
            for key in ('citacao', 'url', 'localizacao', 'data_acesso'):
                if not isinstance(ref.get(key), str) or not ref[key].strip():
                    error('Referência: ' + key + ' ausente.')
            try:
                url = urlsplit(str(ref.get('url', '')))
                if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
                    raise ValueError('URL inválida')
                date.fromisoformat(str(ref.get('data_acesso', '')))
            except ValueError:
                error('Referência: URL pública ou data de acesso inválida.')
    return errors, report


def validar_conjunto(items):
    """Ordena os lotes pelo nome; revisões usam a versão conhecida no banco de destino."""
    errors, reports, lots, current, option_owners = [], [], set(), {}, {}
    for name, payload in sorted(items, key=lambda item: item[0]):
        errs, report = validar(payload)
        errors.extend(f'{name}: {error}' for error in errs)
        reports.append({'arquivo': name, 'questoes': report})
        if errs:
            continue
        lot = payload['lote_id']
        if lot in lots:
            errors.append(f'{name}: lote_id repetido: {lot}')
        lots.add(lot)
        for question in payload['questoes']:
            q = dict(question)
            base = q.pop('versao_base', None)
            body = canon(q)
            previous = current.get(q['id'])
            if previous and previous[1] != body and base != previous[0]:
                errors.append(f"{name}: {q['id']}: revisão exige versao_base={previous[0]}.")
            if not previous or previous[1] != body:
                current[q['id']] = ((previous[0] if previous else (base or 0)) + 1, body)
            for option in q['alternativas']:
                owner = option_owners.setdefault(option['id'], q['id'])
                if owner != q['id']:
                    errors.append(f"{name}: ID de opção reutilizado em questões diferentes: {option['id']}")
    overlap = set(current) & set(option_owners)
    if overlap:
        errors.append('IDs usados simultaneamente para questão e alternativa: ' + ', '.join(sorted(overlap)))
    return errors, reports


def ler_diretorio(path):
    items = []
    for file in sorted(Path(path).glob('*.json')):
        if file.is_symlink() or not file.is_file():
            raise ValueError(f'Entrada deve ser arquivo regular: {file.name}')
        items.append((file.name, carregar_json(file.read_bytes())))
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('caminho', type=Path)
    args = parser.parse_args()
    try:
        if args.caminho.is_dir():
            items = ler_diretorio(args.caminho)
        else:
            items = [(args.caminho.name, carregar_json(args.caminho.read_bytes()))]
        errors, report = validar_conjunto(items)
        print(json.dumps({'checagem_mecanica': 'falhou' if errors else 'aprovada',
                          'lotes': len(items), 'relatorio': report, 'erros': errors}, ensure_ascii=False, indent=2))
        return int(bool(errors))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print('Validação não concluída: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

