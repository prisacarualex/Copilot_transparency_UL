call .venv\Scripts\activate.bat
python -m nuitka --standalone --windows-console-mode=disable --assume-yes-for-downloads ^
  --include-data-dir=".\includes"="includes" ^
  --include-data-dir=".\locales"="locales" ^
  --include-data-file="config.ini"="config.ini" ^
  --include-data-file="LICENSE"="LICENSE" ^
  --include-data-file="README.md"="README.md" ^
  --include-data-file="VERSION"="VERSION" ^
  --remove-output main.py
