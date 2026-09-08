import argparse
from importlib.resources import files
from pathlib import Path
import yaml
from .data.base import DatasetError
from .data.detector import discover, infer_schema
from .data.csv_adapter import CSVAdapter
from .data.pnas_psychophysics import PNASAdapter


def main():
    parser = argparse.ArgumentParser(description='Read-only terminal experimental data explorer')
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--export-dir', type=Path, default=Path.home() / 'psyview-exports')
    parser.add_argument('--detect', action='store_true', help='Report tentative CSV structure without choosing scientific axes')
    parser.add_argument('--save-config', type=Path, help='Save detected YAML for editing; refuses to overwrite or write inside dataset')
    args = parser.parse_args()
    try:
        root = discover(args.data_root)
        if root is None:
            parser.exit(2, 'PNAS data not found. Download/extract the archive, then run:\n  psyview --data-root "C:\\path\\to\\PNAS_Psychopysics_data"\n')
        if not root.is_dir():
            raise DatasetError(f'Data root is not a directory: {root}')
        if args.detect or (not args.config and not (root / 'data/processed/preferred_frequency.csv').is_file()):
            config = infer_schema(root)
            output = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
            if args.save_config:
                destination = args.save_config.resolve()
                if destination.is_relative_to(root):
                    raise DatasetError('Save configuration outside the read-only dataset root.')
                with destination.open('x', encoding='utf-8') as file:
                    file.write(output)
                print(f'Saved tentative configuration: {destination}')
            print(output)
            return
        if args.save_config:
            raise DatasetError('--save-config requires --detect.')
        config = yaml.safe_load(args.config.read_text(encoding='utf-8') if args.config else files('psyview').joinpath('configs/pnas_psychophysics.yaml').read_text(encoding='utf-8'))
        adapter = PNASAdapter(config) if config['dataset'].get('adapter') == 'pnas' else CSVAdapter(config)
        adapter.load(root)
        from .app import PsyView
        PsyView(adapter, args.export_dir).run()
    except (DatasetError, OSError, KeyError, yaml.YAMLError) as exc:
        parser.exit(2, f'Cannot start psyview: {exc}\n')


if __name__ == '__main__':
    main()
