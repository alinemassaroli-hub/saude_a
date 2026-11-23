"""Importa somente lotes de main, com recibo e histórico, no banco local já configurado."""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from validar_lotes import carregar_json, canon, sha256, validar_conjunto, MAX_BYTES

REPO_PATTERN = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA_PATTERN = re.compile(r'[0-9a-f]{40}\Z')


def atomic(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.saude-a-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(raw); file.flush(); os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def api(repo, suffix):
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError('Repositório inválido; esperado proprietario/nome.')
    request = Request(f'https://api.github.com/repos/{repo}/{suffix}', headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'Saude-A-importador/1'})
    # Apenas leitura pública. Nenhum token, chave ou dado do banco é enviado.
    with urlopen(request, timeout=30) as response:
        raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError('Resposta GitHub excede o limite.')
        return json.loads(raw)


def snapshot(repo):
    head = api(repo, 'commits/main')
    commit = head['sha']
    if not SHA_PATTERN.fullmatch(commit):
        raise ValueError('Commit inválido recebido do GitHub.')
    tree = api(repo, f'git/trees/{commit}?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Árvore truncada; nenhum lote foi importado.')
    entries = []
    for item in tree['tree']:
        path = item.get('path', '')
        if not path.startswith('entradas/') or not path.endswith('.json'):
            continue
        name = path.removeprefix('entradas/')
        if '/' in name or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\.json', name):
            raise ValueError('Nome de lote inválido: ' + path)
        if item.get('type') != 'blob' or item.get('mode') != '100644':
            raise ValueError('Lote precisa ser arquivo regular: ' + path)
        if item.get('size', MAX_BYTES + 1) > MAX_BYTES:
            raise ValueError('Lote excede 2 MB: ' + path)
        if not SHA_PATTERN.fullmatch(item['sha']):
            raise ValueError('SHA de arquivo inválido.')
        entries.append((name, item['sha']))
    if len(entries) > 500:
        raise ValueError('Mais de 500 lotes; ajuste controlado do importador necessário.')
    return commit, sorted(entries)


def baixar(repo, blob_sha):
    blob = api(repo, 'git/blobs/' + blob_sha)
    if blob.get('encoding') != 'base64':
        raise ValueError('Codificação de arquivo não suportada.')
    raw = base64.b64decode(''.join(blob['content'].split()), validate=True)
    if len(raw) > MAX_BYTES:
        raise ValueError('Lote excede 2 MB.')
    actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if actual != blob_sha:
        raise ValueError('Conteúdo baixado não corresponde ao SHA do GitHub.')
    return raw


def conferir_recibo(bank_config, raw, payload):
    cloud = Path(bank_config['icloud'])
    receipt_file = cloud / 'recibos' / (sha256(raw) + '.json')
    if not receipt_file.is_file():
        raise ValueError('Consolidação sem recibo do lote; importação não confirmada.')
    receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
    expected_lot = sha256(canon(payload).encode('utf-8'))
    if receipt.get('lote') != expected_lot:
        raise ValueError('Recibo não corresponde ao conteúdo do lote.')
    records = receipt.get('registros', [])
    if len(records) != len(payload['questoes']) or {r['id'] for r in records} != {q['id'] for q in payload['questoes']}:
        raise ValueError('Recibo não contém exatamente os IDs esperados.')
    versions = {r['id']: r['versao'] for r in records}
    database = Path(bank_config['banco']) / 'banco.sqlite'
    # Confere a revisão exata, inclusive após eventual revisão posterior no banco.
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        for original in payload['questoes']:
            q = dict(original)
            q.pop('versao_base', None)
            row = db.execute('SELECT payload FROM revisoes WHERE id=? AND versao=?',
                             (q['id'], versions[q['id']])).fetchone()
            if not row or json.loads(row[0]) != q:
                raise ValueError('Conteúdo persistido diverge do lote: ' + q['id'])
    return receipt


def processar(config, workdir, verificar=False, remote_snapshot=snapshot, download=baixar, runner=subprocess.run):
    repo = config['repositorio']
    if not REPO_PATTERN.fullmatch(repo):
        raise ValueError('Repositório inválido.')
    workdir = Path(workdir)
    bank_config_path = Path(config['config_banco'])
    bank_config = json.loads(bank_config_path.read_text(encoding='utf-8'))
    for key in ('banco', 'icloud'):
        if not Path(bank_config[key]).is_absolute() or not Path(bank_config[key]).is_dir():
            raise ValueError('Banco configurado indisponível: ' + key)
    entries = Path(bank_config['icloud']) / 'entradas'
    if not entries.is_dir():
        raise ValueError('Pasta entradas indisponível; não foi criado banco alternativo.')
    consolidator = Path(config['consolidador'])
    if not consolidator.is_absolute() or not consolidator.is_file():
        raise ValueError('Consolidador local indisponível.')
    state_path = workdir / 'estado-github.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.is_file() else {'repositorio': repo, 'lotes': {}}
    if state.get('repositorio') != repo:
        raise ValueError('O estado pertence a outro repositório; use configuração separada.')
    commit, remote_files = remote_snapshot(repo)
    names = {name for name, _ in remote_files}
    missing = set(state['lotes']) - names
    if missing:
        raise ValueError('Lotes já importados foram removidos ou renomeados: ' + ', '.join(sorted(missing)))
    loaded, raw_files, new = [], {}, []
    cache = workdir / 'cache'
    for name, blob_sha in remote_files:
        prior = state['lotes'].get(name)
        if prior and prior['blob_sha'] != blob_sha:
            raise ValueError('Lote já importado foi alterado. Envie revisão em novo arquivo: ' + name)
        cache_file = cache / (blob_sha + '.json')
        if cache_file.is_file():
            raw = cache_file.read_bytes()
            actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if actual != blob_sha:
                raise ValueError('Cache divergente; remova apenas o arquivo corrompido: ' + str(cache_file))
        else:
            raw = download(repo, blob_sha)
            if not verificar:
                atomic(cache_file, raw)
        payload = carregar_json(raw)
        loaded.append((name, payload)); raw_files[name] = raw
        if not prior:
            new.append(name)
    errors, _ = validar_conjunto(loaded)
    if errors:
        raise ValueError('Lotes rejeitados antes da importação: ' + '; '.join(errors))
    result = {'repositorio': repo, 'commit': commit, 'lotes_em_main': len(loaded),
              'lotes_novos': new, 'importados': [], 'modo': 'verificação sem importação' if verificar else 'importação'}
    if verificar:
        return result
    for name, payload in loaded:
        if name not in new:
            continue
        raw = raw_files[name]
        destination = entries / ('github_' + name)
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError('Entrada local com conteúdo diferente; nada sobrescrito: ' + destination.name)
        if not destination.exists():
            atomic(destination, raw)
        completed = runner([config['python'], '-B', str(consolidator), '--config', str(bank_config_path)],
                           capture_output=True, text=True, timeout=300)
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ValueError('Consolidação não concluída; lote preservado para nova tentativa: ' + detail)
        receipt = conferir_recibo(bank_config, raw, payload)
        state['lotes'][name] = {'blob_sha': dict(remote_files)[name], 'sha256': sha256(raw),
                               'lote': receipt['lote'], 'registros': receipt['registros'], 'commit': commit}
        atomic(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        result['importados'].append({'arquivo': name, 'registros': receipt['registros']})
    state['ultimo_commit'] = commit
    state['verificado_em'] = datetime.now(timezone.utc).isoformat()
    atomic(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    atomic(workdir / 'ultimo_resultado.json', (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--verificar', action='store_true', help='Consulta e valida; não escreve no banco nem no iCloud.')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        workdir = args.config.resolve().parent
        with (workdir / 'github.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Já existe uma importação GitHub em andamento.'); return 0
            result = processar(config, workdir, args.verificar)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        print(f'GitHub respondeu HTTP {exc.code}; banco preservado. Confira acesso e limite da API.', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RecursionError, URLError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print('Importação GitHub não concluída: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
