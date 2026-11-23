"""Configura a ponte GitHub → banco existente e, opcionalmente, ativa a rotina no macOS."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'br.saudea.github'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-banco', type=Path, required=True)
    parser.add_argument('--repositorio', default='alinemassaroli-hub/saude_a')
    parser.add_argument('--ativar', action='store_true', help='Ativa verificação horária via launchd no macOS.')
    args = parser.parse_args()
    try:
        path = args.config_banco.expanduser().resolve(strict=True)
        bank = json.loads(path.read_text(encoding='utf-8'))
        consolidator = Path(bank['operacao']) / 'consolidar.py'
        python = bank.get('python', sys.executable)
        if not consolidator.is_file() or not os.access(python, os.X_OK):
            raise ValueError('Python ou consolidador do banco indisponível.')
        local = ROOT / '.local'
        local.mkdir(exist_ok=True, mode=0o700)
        config_path = local / 'github.json'
        content = {'repositorio': args.repositorio, 'config_banco': str(path),
                   'consolidador': str(consolidator), 'python': python}
        config_path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        config_path.chmod(0o600)
        command = [python, '-B', str(ROOT / 'scripts/sincronizar_github.py'), '--config', str(config_path)]
        plist_path = local / (LABEL + '.plist')
        job = {'Label': LABEL, 'ProgramArguments': command, 'WorkingDirectory': str(ROOT),
               'RunAtLoad': True, 'StartInterval': 3600, 'ThrottleInterval': 60, 'ProcessType': 'Background',
               'EnvironmentVariables': {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'},
               'StandardOutPath': str(local / 'github.log'), 'StandardErrorPath': str(local / 'github-erros.log')}
        plist_path.write_bytes(plistlib.dumps(job))
        if args.ativar:
            if sys.platform != 'darwin':
                raise ValueError('Ativação automática disponível no macOS. Em Linux, use o comando documentado no cron.')
            subprocess.run(command + ['--verificar'], check=True, timeout=180)
            service = f'gui/{os.getuid()}/{LABEL}'
            loaded = subprocess.run(['launchctl', 'print', service], capture_output=True, text=True)
            if loaded.returncode == 0:
                if str(plist_path) not in loaded.stdout:
                    raise ValueError('Já existe rotina com este nome em outro local; confira antes de substituir.')
                print('Rotina já ativa para este projeto.')
            else:
                subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(plist_path)], check=True)
                print('Rotina horária ativada. Será retomada enquanto este usuário estiver conectado ao macOS.')
        else:
            print('Configuração preparada; rotina ainda não ativada.')
        print(config_path)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print('Configuração não concluída: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

