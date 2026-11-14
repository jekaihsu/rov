"""Check only added PR lines in first-party viewer JavaScript."""
import re
import subprocess
import sys

base = sys.argv[1]
diff = subprocess.check_output([
    'git', 'diff', '--no-ext-diff', '--unified=0', base, 'HEAD', '--',
    'simulator/viewer/**/*.js', 'simulator/viewer/*.js',
    ':!simulator/viewer/vendor/**',
], text=True)
file = ''
line = 0
errors = []
for text in diff.splitlines():
    if text.startswith('+++ b/'):
        file = text[6:]
    elif text.startswith('@@'):
        line = int(re.search(r'\+(\d+)', text).group(1))
    elif text.startswith('+'):
        if len(text[1:]) > 160:
            errors.append(f'{file}:{line}: added line exceeds 160 characters')
        line += 1
    elif text.startswith(' '):
        line += 1
print('\n'.join(errors) if errors else 'Changed JavaScript line widths passed')
sys.exit(bool(errors))
