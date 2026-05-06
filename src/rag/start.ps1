# start.ps1

# 文字化け防止のためエンコーディングをUTF-8に設定
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   RAG Project Launcher (PowerShell)      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Pythonの確認
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Pythonが見つかりません。Pythonをインストールしてください。"
    Pause
    exit
}

# 仮想環境の確認とアクティベート (一般的な名前: .venv, venv)
$venvParams = @(".venv", "venv")
$venvFound = $false

foreach ($v in $venvParams) {
    if (Test-Path "$v\Scripts\Activate.ps1") {
        Write-Host "仮想環境 ($v) を検出しました。アクティベートします..." -ForegroundColor Green
        & ".\$v\Scripts\Activate.ps1"
        $venvFound = $true
        break
    }
}

if (-not $venvFound) {
    Write-Warning "仮想環境が見つかりません。システムにインストールされたPythonを使用します。"
    Write-Host "仮想環境を作成するには 'python -m venv .venv' を実行してください。" -ForegroundColor Gray
}

function Show-Menu {
    Write-Host "`n実行したい操作の番号を入力してください:" -ForegroundColor Yellow
    Write-Host "1. [初期構築] 知識ベースの作成 (build_knowledge.py)"
    Write-Host "2. [アプリ起動] RAGエージェントの起動 (streamlit run app.py)"
    Write-Host "3. [CLI] チャットの実行 (main.py)"
    Write-Host "4. [テスト] LLM接続テスト (load_prompt.py)"
    Write-Host "5. [管理] バックアップとリストア (manage_kb.py)"
    Write-Host "q. 終了"
}

do {
    Show-Menu
    $choice = Read-Host "選択"
    
    switch ($choice) {
        "1" {
            Write-Host "`n--- 知識ベース構築を開始します ---" -ForegroundColor Cyan
            python build_knowledge.py
            Write-Host "処理が完了しました。" -ForegroundColor Green
        }
        "2" {
            Write-Host "`n--- Streamlitアプリを起動します ---" -ForegroundColor Cyan
            Write-Host "停止するには Ctrl+C を押してください。" -ForegroundColor Gray
            python -m streamlit run app.py
        }
        "3" {
            Write-Host "`n--- CLIチャットを開始します ---" -ForegroundColor Cyan
            python main.py
        }
        "4" {
            Write-Host "`n--- 接続テストを実行します ---" -ForegroundColor Cyan
            python load_prompt.py
        }
        "5" {
            Write-Host "`n--- バックアップ管理 ---" -ForegroundColor Cyan
            $action = Read-Host "操作を入力してください (b: backup / r: restore)"
            if ($action -eq "b") {
                python manage_kb.py backup
            } elseif ($action -eq "r") {
                python manage_kb.py restore
            } else {
                Write-Warning "無効な操作です。"
            }
        }
        "q" {
            Write-Host "終了します。"
            break
        }
        Default {
            Write-Warning "無効な入力です。もう一度入力してください。"
        }
    }
} while ($choice -ne 'q')