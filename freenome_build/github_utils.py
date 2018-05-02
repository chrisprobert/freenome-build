def repo_name()
    repo_name = os.path.basename(
        subprocess.run(
            'git rev-parse --show-toplevel',
            shell=True,
            stdout=subprocess.PIPE
        ).stdout.strip().decode('utf8')).lower().replace('-', '_')