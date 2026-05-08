#!/bin/bash

##############################################################################
#
# Enterprise Security Platform - Automation Scripts Suite
# スクリプト集: バックアップ、リカバリ、デプロイ、監視
#
# 用途: 本番環境の自動運用
# 作成日: 2026-04-17
# バージョン: 1.0
#
##############################################################################

set -euo pipefail

# ============================================================================
# 設定セクション
# ============================================================================

PROJECT_ROOT="/home/abemc/project_root"
BACKUP_DIR="${PROJECT_ROOT}/backups"
LOGS_DIR="${PROJECT_ROOT}/logs"
SCRIPTS_DIR="${PROJECT_ROOT}/tools/automation"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Kubernetes 設定
K8S_NAMESPACE="production"
K8S_CLUSTER="esp-prod-cluster"

# データベース設定
DB_HOST="db-primary.internal"
DB_PORT="5432"
DB_NAME="esp_platform"
DB_USER="esp_admin"
BACKUP_RETENTION_DAYS=30

# Slack 通知
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# ============================================================================
# ログ関数
# ============================================================================

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $*" | tee -a "${LOGS_DIR}/automation.log"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "${LOGS_DIR}/automation.log" >&2
}

log_success() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $*" | tee -a "${LOGS_DIR}/automation.log"
}

# ============================================================================
# Slack 通知関数
# ============================================================================

notify_slack() {
    local message="$1"
    local color="${2:-good}"
    
    if [[ -z "$SLACK_WEBHOOK" ]]; then
        return 0
    fi
    
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"attachments\": [{
                \"color\": \"$color\",
                \"title\": \"ESP Automation Alert\",
                \"text\": \"$message\",
                \"ts\": $(date +%s)
            }]
        }" || true
}

# ============================================================================
# 1. バックアップスクリプト
# ============================================================================

backup_database() {
    log_info "🔄 Starting database backup..."
    
    mkdir -p "${BACKUP_DIR}/database/${TIMESTAMP}"
    
    # PostgreSQL ダンプ
    BACKUP_FILE="${BACKUP_DIR}/database/${TIMESTAMP}/backup.sql"
    
    log_info "Dumping PostgreSQL database..."
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --verbose \
        > "$BACKUP_FILE" 2>&1
    
    # バックアップサイズ確認
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Backup completed. Size: $BACKUP_SIZE"
    
    # 暗号化 (AES-256)
    log_info "🔐 Encrypting backup..."
    openssl enc -aes-256-cbc -salt -in "$BACKUP_FILE" \
        -out "${BACKUP_FILE}.enc" \
        -k "${BACKUP_ENCRYPTION_KEY:-default_key_change_me}"
    
    # S3 にアップロード (別リージョン)
    log_info "📤 Uploading to S3..."
    aws s3 cp "${BACKUP_FILE}.enc" \
        "s3://esp-backup-secondary/$(date +%Y/%m/%d)/${TIMESTAMP}.sql.enc" \
        --region us-west-2 \
        --sse AES256 \
        --storage-class GLACIER || log_error "S3 upload failed"
    
    # ローカルバックアップ削除
    rm -f "$BACKUP_FILE" "${BACKUP_FILE}.enc"
    
    log_success "✅ Database backup completed successfully"
    notify_slack "✅ Database backup completed: $BACKUP_SIZE" "good"
}

backup_kubernetes_config() {
    log_info "🔄 Backing up Kubernetes configurations..."
    
    BACKUP_K8S_DIR="${BACKUP_DIR}/kubernetes/${TIMESTAMP}"
    mkdir -p "$BACKUP_K8S_DIR"
    
    # ConfigMap & Secrets バックアップ
    kubectl get configmaps -n "$K8S_NAMESPACE" -o yaml > \
        "${BACKUP_K8S_DIR}/configmaps.yaml"
    
    kubectl get secrets -n "$K8S_NAMESPACE" -o yaml > \
        "${BACKUP_K8S_DIR}/secrets.yaml"
    
    # Deployment 情報
    kubectl get deployments -n "$K8S_NAMESPACE" -o yaml > \
        "${BACKUP_K8S_DIR}/deployments.yaml"
    
    # Service 情報
    kubectl get svc -n "$K8S_NAMESPACE" -o yaml > \
        "${BACKUP_K8S_DIR}/services.yaml"
    
    tar -czf "${BACKUP_K8S_DIR}.tar.gz" -C "${BACKUP_DIR}/kubernetes" "${TIMESTAMP}"
    
    log_success "✅ Kubernetes backup completed"
}

cleanup_old_backups() {
    log_info "🧹 Cleaning up old backups..."
    
    find "${BACKUP_DIR}" -type f -name "*.enc" -mtime "+${BACKUP_RETENTION_DAYS}" -delete
    find "${BACKUP_DIR}" -type d -empty -delete
    
    log_success "✅ Backup cleanup completed"
}

# ============================================================================
# 2. リカバリスクリプト
# ============================================================================

restore_database() {
    local backup_file="$1"
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    log_info "⚠️  CRITICAL: Starting database restore from $backup_file"
    
    # 復号化
    log_info "🔓 Decrypting backup..."
    openssl enc -aes-256-cbc -d -in "${backup_file}.enc" \
        -out "${backup_file}.dec" \
        -k "${BACKUP_ENCRYPTION_KEY:-default_key_change_me}"
    
    # リストア
    log_info "Restoring database..."
    pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        "${backup_file}.dec" 2>&1 | tee -a "${LOGS_DIR}/restore.log"
    
    # ファイル削除
    rm -f "${backup_file}.dec"
    
    log_success "✅ Database restore completed"
    notify_slack "⚠️ Database restored from backup" "warning"
}

# ============================================================================
# 3. デプロイメントスクリプト
# ============================================================================

deploy_application() {
    local version="${1:-latest}"
    local env="${2:-production}"
    
    log_info "🚀 Starting deployment: version=$version, env=$env"
    
    # イメージビルド
    log_info "🔨 Building Docker image..."
    docker build -t "esp-platform:${version}" \
        -f "${PROJECT_ROOT}/Dockerfile" \
        "${PROJECT_ROOT}" 2>&1 | tail -5
    
    # ECR にプッシュ
    log_info "📤 Pushing to ECR..."
    aws ecr get-login-password --region us-east-1 | \
        docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
    
    docker tag "esp-platform:${version}" \
        "123456789.dkr.ecr.us-east-1.amazonaws.com/esp-platform:${version}"
    
    docker push "123456789.dkr.ecr.us-east-1.amazonaws.com/esp-platform:${version}"
    
    # Kubernetes デプロイ (Canary)
    log_info "📋 Deploying to Kubernetes (canary)..."
    
    kubectl set image deployment/esp-api \
        esp-api="123456789.dkr.ecr.us-east-1.amazonaws.com/esp-platform:${version}" \
        -n "$K8S_NAMESPACE" \
        --record
    
    # ロールアウト 監視
    log_info "⏳ Monitoring rollout..."
    kubectl rollout status deployment/esp-api \
        -n "$K8S_NAMESPACE" \
        --timeout=10m
    
    log_success "✅ Deployment completed successfully"
    notify_slack "✅ Deployment completed: version $version" "good"
}

# Canary デプロイメント
canary_deploy() {
    local version="$1"
    
    log_info "🎯 Starting Canary deployment: version=$version"
    
    # Stage 1: 5% トラフィック
    log_info "Stage 1: 5% traffic"
    kubectl patch deployment esp-api -n "$K8S_NAMESPACE" -p \
        '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"5%"}}}}'
    
    sleep 300  # 5 分監視
    
    if ! check_health; then
        log_error "❌ Health check failed at 5%"
        rollback_deployment
        return 1
    fi
    
    # Stage 2: 25% トラフィック
    log_info "Stage 2: 25% traffic"
    sleep 300
    
    if ! check_health; then
        log_error "❌ Health check failed at 25%"
        rollback_deployment
        return 1
    fi
    
    # Stage 3: 100% トラフィック
    log_info "Stage 3: 100% traffic"
    kubectl rollout resume deployment/esp-api -n "$K8S_NAMESPACE"
    
    log_success "✅ Canary deployment completed"
}

rollback_deployment() {
    log_error "🔙 Rolling back deployment..."
    kubectl rollout undo deployment/esp-api -n "$K8S_NAMESPACE"
    notify_slack "⚠️ Deployment rolled back" "danger"
}

check_health() {
    local health_check_url="http://api-gateway.internal/health"
    local max_attempts=5
    local attempt=0
    
    while (( attempt < max_attempts )); do
        if curl -sf "$health_check_url" > /dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 10
    done
    
    return 1
}

# ============================================================================
# 4. 監視スクリプト
# ============================================================================

check_system_health() {
    log_info "🏥 Running system health check..."
    
    local failed_checks=0
    
    # API エンドポイント確認
    log_info "Checking API endpoints..."
    if ! curl -sf "http://api-gateway.internal/health" > /dev/null; then
        log_error "❌ API Gateway unreachable"
        ((failed_checks++))
    fi
    
    # DB 接続確認
    log_info "Checking database connection..."
    if ! PGPASSWORD="$DB_USER" psql -h "$DB_HOST" -U "$DB_USER" \
        -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
        log_error "❌ Database connection failed"
        ((failed_checks++))
    fi
    
    # Kubernetes ノード確認
    log_info "Checking Kubernetes nodes..."
    local not_ready_nodes=$(kubectl get nodes -n "$K8S_NAMESPACE" \
        | grep -v Ready | grep -v "STATUS" | wc -l)
    
    if (( not_ready_nodes > 0 )); then
        log_error "❌ $not_ready_nodes nodes not ready"
        ((failed_checks++))
    fi
    
    # Redis 確認
    log_info "Checking Redis cache..."
    if ! redis-cli -h cache.internal ping | grep -q PONG; then
        log_error "❌ Redis unreachable"
        ((failed_checks++))
    fi
    
    if (( failed_checks == 0 )); then
        log_success "✅ All health checks passed"
        notify_slack "✅ System health check: All systems operational" "good"
        return 0
    else
        log_error "❌ $failed_checks health checks failed"
        notify_slack "⚠️ System health check: $failed_checks failures" "danger"
        return 1
    fi
}

monitor_metrics() {
    log_info "📊 Collecting system metrics..."
    
    local metrics_file="${LOGS_DIR}/metrics_${TIMESTAMP}.json"
    
    {
        echo "{"
        echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
        echo "  \"kubernetes\": {"
        
        # Node リソース
        echo "    \"nodes\": $(kubectl get nodes -o json | jq '.items | length'),"
        
        # Pod リソース
        echo "    \"pods_running\": $(kubectl get pods -n "$K8S_NAMESPACE" \
            --field-selector=status.phase=Running -o json | jq '.items | length'),"
        
        # CPU/Memory 使用率
        echo "    \"node_resources\": $(kubectl top nodes --no-headers | \
            jq -s '[.[] | {node: .metadata.name, cpu: .usage.cpu, memory: .usage.memory}]')"
        echo "  },"
        
        # Prometheus メトリクス
        echo "  \"prometheus\": {"
        echo "    \"api_latency_p95\": $(curl -s 'http://prometheus:9090/api/v1/query?query=histogram_quantile(0.95,api_latency_seconds)' \
            | jq '.data.result[0].value[1]'),"
        echo "    \"error_rate\": $(curl -s 'http://prometheus:9090/api/v1/query?query=rate(errors_total[5m])' \
            | jq '.data.result[0].value[1]')"
        echo "  }"
        echo "}"
    } > "$metrics_file"
    
    log_success "✅ Metrics collected: $metrics_file"
}

# ============================================================================
# 5. 定期メンテナンススクリプト
# ============================================================================

rotate_logs() {
    log_info "🔄 Rotating logs..."
    
    find "${LOGS_DIR}" -name "*.log" -mtime +30 -delete
    
    # ログ圧縮
    for log_file in "${LOGS_DIR}"/*.log; do
        if [[ -f "$log_file" && -s "$log_file" ]]; then
            gzip "$log_file" || true
        fi
    done
    
    log_success "✅ Log rotation completed"
}

cleanup_cache() {
    log_info "🧹 Cleaning up cache..."
    
    # Redis キャッシュクリア (部分的)
    redis-cli -h cache.internal FLUSHDB ASYNC 2>/dev/null || true
    
    # ローカルキャッシュ削除
    find /var/cache/esp-platform -type f -mtime +7 -delete 2>/dev/null || true
    
    log_success "✅ Cache cleanup completed"
}

# ============================================================================
# 6. セキュリティスキャン
# ============================================================================

run_security_scan() {
    log_info "🔒 Running security scans..."
    
    local scan_dir="${LOGS_DIR}/security_scan_${TIMESTAMP}"
    mkdir -p "$scan_dir"
    
    # コンテナイメージスキャン
    log_info "Scanning container images with Trivy..."
    trivy image --severity HIGH,CRITICAL \
        "esp-platform:latest" > "${scan_dir}/trivy_report.txt" || true
    
    # OWASP Dependency チェック
    log_info "Checking dependencies with OWASP..."
    dependency-check.sh --project "ESP" \
        --scan "${PROJECT_ROOT}/src" \
        --format JSON \
        --out "${scan_dir}/owasp_report.json" || true
    
    # SonarQube 静的解析
    log_info "Running SonarQube analysis..."
    sonar-scanner \
        -Dsonar.projectKey=esp-platform \
        -Dsonar.sources="${PROJECT_ROOT}/src" \
        -Dsonar.host.url=http://sonarqube:9000 \
        > "${scan_dir}/sonar_report.txt" 2>&1 || true
    
    log_success "✅ Security scans completed: $scan_dir"
    notify_slack "✅ Security scans completed" "good"
}

# ============================================================================
# メイン実行
# ============================================================================

main() {
    local command="${1:-help}"
    
    case "$command" in
        backup-db)
            backup_database
            backup_kubernetes_config
            cleanup_old_backups
            ;;
        
        restore-db)
            restore_database "${2:-}"
            ;;
        
        deploy)
            deploy_application "${2:-v1.0.0}" "${3:-production}"
            ;;
        
        canary)
            canary_deploy "${2:-v1.0.0}"
            ;;
        
        health)
            check_system_health
            ;;
        
        metrics)
            monitor_metrics
            ;;
        
        maintenance)
            rotate_logs
            cleanup_cache
            ;;
        
        security)
            run_security_scan
            ;;
        
        all)
            backup_database
            backup_kubernetes_config
            check_system_health
            monitor_metrics
            ;;
        
        help|*)
            cat << 'EOF'
ESP Platform Automation Script Suite v1.0

Usage: $0 <command> [options]

Commands:
  backup-db              - Backup database and Kubernetes configs
  restore-db <file>      - Restore database from backup
  deploy <version> [env] - Deploy application version
  canary <version>       - Canary deployment
  health                 - Check system health
  metrics                - Collect system metrics
  maintenance            - Rotate logs and cleanup cache
  security               - Run security scans
  all                    - Run all operations
  help                   - Show this help message

Environment Variables:
  SLACK_WEBHOOK_URL      - Slack webhook for notifications
  BACKUP_ENCRYPTION_KEY  - Encryption key for backups

Examples:
  $0 backup-db
  $0 deploy v1.1.0 production
  $0 canary v1.1.0
  $0 health
EOF
            ;;
    esac
}

# スクリプト実行
main "$@"
