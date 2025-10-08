.PHONY: help k80-detect k80-warmup k80-burnin k80-build k80-up k80-down k80-logs

help: ## Show this help message
	@echo "HAssistant - Tesla K80 GPU Management"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

k80-detect: ## Detect K80 GPUs and show their indices
	@echo "════════════════════════════════════════════════════════════"
	@echo "Detecting Tesla K80 GPUs..."
	@echo "════════════════════════════════════════════════════════════"
	@nvidia-smi --query-gpu=index,name,memory.total,compute_cap --format=csv,noheader | grep -i "K80" || \
		(echo "⚠️  No Tesla K80 GPUs detected" && nvidia-smi --query-gpu=index,name,memory.total --format=csv)

k80-build: ## Build vision-worker Docker image
	@echo "Building vision-worker image..."
	docker build -t hassistant/vision-worker:latest ./services/vision-worker/

k80-warmup: k80-build ## Run warmup tests on both K80 workers
	@echo "════════════════════════════════════════════════════════════"
	@echo "Running K80 warmup tests..."
	@echo "════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Testing screen worker (GPU ${VISION_SCREEN_CUDA_DEVICE:-2})..."
	@docker run --rm --gpus "device=${VISION_SCREEN_CUDA_DEVICE:-2}" \
		-e VISION_CUDA_DEVICE=${VISION_SCREEN_CUDA_DEVICE:-2} \
		-e VISION_ROLE=screen \
		hassistant/vision-worker:latest \
		python3 -c "from app.main import setup_gpu, run_warmup; setup_gpu(); run_warmup()" || \
		echo "⚠️  Screen worker warmup failed"
	@echo ""
	@echo "Testing room worker (GPU ${VISION_ROOM_CUDA_DEVICE:-3})..."
	@docker run --rm --gpus "device=${VISION_ROOM_CUDA_DEVICE:-3}" \
		-e VISION_CUDA_DEVICE=${VISION_ROOM_CUDA_DEVICE:-3} \
		-e VISION_ROLE=room \
		hassistant/vision-worker:latest \
		python3 -c "from app.main import setup_gpu, run_warmup; setup_gpu(); run_warmup()" || \
		echo "⚠️  Room worker warmup failed"
	@echo ""
	@echo "For detailed health check, run: make k80-up && curl http://localhost:8089/health"

k80-burnin: k80-build ## Run 10-minute stress test on both K80 GPUs
	@bash ./scripts/k80_burnin.sh

k80-up: k80-build ## Start vision-worker services
	@echo "Starting vision-worker services..."
	docker compose up -d vision-screen vision-room

k80-down: ## Stop vision-worker services
	@echo "Stopping vision-worker services..."
	docker compose stop vision-screen vision-room

k80-logs: ## Follow logs from vision-worker services
	docker compose logs -f vision-screen vision-room

# Additional utility targets
k80-health: ## Check health of running workers
	@echo "Screen worker health:"
	@curl -s http://localhost:8089/health | python3 -m json.tool || echo "⚠️  Screen worker not responding"
	@echo ""
	@echo "Room worker health:"
	@curl -s http://localhost:8090/health | python3 -m json.tool || echo "⚠️  Room worker not responding"

k80-stats: ## Show real-time GPU statistics
	@watch -n 1 nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv
