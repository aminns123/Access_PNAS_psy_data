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
    parser.add_argument('--debug', action='store_true', help='Write verbose diagnostics to the temporary psyview.log file')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--export-dir', type=Path, default=Path.home() / 'psyview-exports')
    parser.add_argument('--detect', action='store_true', help='Report tentative CSV structure without choosing scientific axes')
    parser.add_argument('--save-config', type=Path, help='Save detected YAML for editing; refuses to overwrite or write inside dataset')
    args = parser.parse_args()
    import logging
    from .plotting.matplotlib_plots import LOG_PATH
    logging.basicConfig(filename=LOG_PATH, encoding='utf-8', level=logging.DEBUG if args.debug else logging.WARNING,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    try:
        if args.data_root is None:
            if args.detect or args.config or args.save_config:
                raise DatasetError('--detect/--config/--save-config require --data-root.')
            from .ui.dataset_browser import DatasetBrowser
            adapter = DatasetBrowser().run()
            if adapter is None:
                return
            from .preferences import remember_dataset
            remember_dataset(adapter.root)
            from .app import PsyView
            PsyView(adapter, args.export_dir).run()
            return
        root = discover(args.data_root)
        if not root.is_dir():
            raise DatasetError(f'Data root is not a directory: {root}')
        if args.detect:
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
        if args.config:
            config = yaml.safe_load(args.config.read_text(encoding='utf-8'))
            adapter = PNASAdapter(config) if config['dataset'].get('adapter') == 'pnas' else CSVAdapter(config)
            adapter.load(root)
        else:
            from .data.registry import open_dataset
            adapter = open_dataset(root)
        from .preferences import remember_dataset
        remember_dataset(root)
        from .app import PsyView
        PsyView(adapter, args.export_dir).run()
    except (DatasetError, OSError, KeyError, yaml.YAMLError) as exc:
        parser.exit(2, f'Cannot start psyview: {exc}\n')


if __name__ == '__main__':
    main()
