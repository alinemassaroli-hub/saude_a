"""Cria um rascunho com UUIDs e classificação aprovada; nunca registra no banco."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from validar_lotes import catalogo, SLUG


def novo(subcategoria, autor, quantidade=1):
    taxonomy = catalogo()
    if subcategoria not in taxonomy:
        raise ValueError('Subcategoria inexistente: consulte references/taxonomia.json.')
    if not autor.strip() or not 1 <= quantidade <= 100:
        raise ValueError('Informe autor e quantidade de 1 a 100.')
    row = taxonomy[subcategoria]
    now = datetime.now(timezone.utc)
    lot = now.strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:12]
    questions = []
    for _ in range(quantidade):
        qid = 'SA' + subcategoria.replace('.', '_') + '_' + str(uuid.uuid4())
        options = [{'id': f'{qid}_OP{i:02d}', 'texto': ''} for i in range(1, 6)]
        questions.append({
            'id': qid, 'profissao': 'Enfermagem', 'publico': '',
            **{key: row[key] for key in ('categoria_codigo', 'categoria', 'subcategoria_codigo', 'subcategoria')},
            'tema': '', 'objetivo': '', 'nivel_cognitivo': '',
            'dificuldade': 'Moderada', 'justificativa': '', 'prova_banca': 'Questão original; prova não especificada.',
            'tipo_resposta': 'unica', 'enunciado': '', 'alternativas': options,
            'gabarito': [{'id': options[0]['id'], 'texto': ''}],
            'explicacao': '', 'dica_professor': '',
            'referencias': [{'citacao': '', 'url': '', 'localizacao': '', 'data_acesso': now.date().isoformat()}],
            'data_validacao': now.date().isoformat(), 'status_editorial': 'Rascunho; revisão especializada pendente',
            'auditoria': ''})
    return {'schema_version': 1, 'lote_id': lot, 'titulo': '', 'autor': autor,
            'origem': 'GitHub: Saúde A — contribuição original',
            'data_criacao': now.isoformat(), 'questoes': questions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subcategoria', required=True)
    parser.add_argument('--autor', required=True)
    parser.add_argument('--quantidade', type=int, default=1)
    parser.add_argument('--saida', type=Path, default=Path('entradas'))
    args = parser.parse_args()
    try:
        payload = novo(args.subcategoria, args.autor, args.quantidade)
        args.saida.mkdir(parents=True, exist_ok=True)
        path = args.saida / (payload['lote_id'] + '.json')
        with path.open('x', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write('\n')
        print(path)
        print('Rascunho criado. Preencha os campos e ajuste o gabarito antes de validar.')
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
