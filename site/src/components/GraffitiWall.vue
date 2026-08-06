<template>
  <div class="graffiti-wall mt-12 max-w-4xl mx-auto px-5">
    <!-- 标题栏 -->
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-xl font-bold text-primary">涂鸦墙</h2>
      <span class="text-xs text-base-content/50">每天清空，随意涂鸦</span>
    </div>

    <!-- 工具栏 -->
    <div class="flex flex-wrap items-center gap-3 mb-3 p-3 bg-base-100 rounded-box shadow-sm">
      <div class="flex items-center gap-2">
        <label class="text-xs text-base-content/60">颜色</label>
        <div class="relative">
          <input
            type="color"
            v-model="color"
            class="w-8 h-8 rounded-full border-2 border-base-300 cursor-pointer p-0"
            :style="{ backgroundColor: color }"
            title="选择画笔颜色"
          />
        </div>
        <div class="flex gap-1.5 ml-1">
          <button
            v-for="c in presetColors"
            :key="c"
            class="w-5 h-5 rounded-full border-2 cursor-pointer transition-transform hover:scale-110"
            :class="color === c ? 'border-primary scale-110 shadow-sm' : 'border-base-300'"
            :style="{ backgroundColor: c }"
            @click="color = c"
            :title="c"
          ></button>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <label for="brush-size" class="text-xs text-base-content/60">粗细</label>
        <input
          id="brush-size"
          type="range"
          v-model.number="brushSize"
          min="1"
          max="20"
          class="range range-xs range-primary w-20"
          title="画笔粗细"
        />
        <span class="text-xs text-base-content/40 w-5 text-right">{{ brushSize }}</span>
      </div>

      <div class="flex-1"></div>
    </div>

    <!-- 画布区域 -->
    <div class="canvas-wrapper bg-white rounded-box shadow-inner border border-base-300 overflow-hidden">
      <canvas
        ref="canvasRef"
        class="block w-full cursor-crosshair"
        :style="{ aspectRatio: '2/1', maxHeight: '400px' }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointerleave="onPointerUp"
        @pointercancel="onPointerUp"
      ></canvas>
    </div>

    <!-- 底部状态 -->
    <div class="flex items-center gap-2 mt-2">
      <span class="inline-block w-3 h-3 rounded-full border border-base-300" :style="{ backgroundColor: color }"></span>
      <span class="text-xs text-base-content/40">{{ savingStatus }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from "vue";

const API_URL = "/api/graffiti";

const canvasRef = ref(null);
const color = ref("#003087");
const brushSize = ref(3);
const savingStatus = ref("准备就绪");

const presetColors = ["#003087", "#e87722", "#dc2626", "#16a34a", "#0891b2", "#7c3aed", "#000000", "#6b7280"];

let ctx = null;
let isDrawing = false;
let lastX = 0;
let lastY = 0;
let resizeObserver = null;

// ── Canvas 尺寸管理 ──
function resizeCanvas() {
  const canvas = canvasRef.value;
  if (!canvas) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const rect = canvas.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;

  if (canvas.width === w * dpr && canvas.height === h * dpr) return;

  // 备份当前画面
  const existingImage = canvas.width > 0 ? canvas.toDataURL("image/png") : null;

  canvas.width = w * dpr;
  canvas.height = h * dpr;

  // 恢复画面 + 设置缩放
  const context = canvas.getContext("2d");
  context.scale(dpr, dpr);
  context.lineCap = "round";
  context.lineJoin = "round";

  if (existingImage) {
    const img = new Image();
    img.onload = () => {
      context.drawImage(img, 0, 0, w, h);
    };
    img.src = existingImage;
  }
}

// ── 坐标换算 ──
function getCanvasPoint(e) {
  const canvas = canvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
}

// ── 绘图事件 ──
function onPointerDown(e) {
  e.preventDefault();
  isDrawing = true;
  const pt = getCanvasPoint(e);
  lastX = pt.x;
  lastY = pt.y;

  ctx = canvasRef.value.getContext("2d");
  ctx.strokeStyle = color.value;
  ctx.lineWidth = brushSize.value;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  // 画一个点（mousedown 不移动时也留个点）
  ctx.beginPath();
  ctx.arc(pt.x, pt.y, brushSize.value / 2, 0, Math.PI * 2);
  ctx.fillStyle = color.value;
  ctx.fill();
}

function onPointerMove(e) {
  if (!isDrawing) return;
  e.preventDefault();

  const pt = getCanvasPoint(e);
  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(pt.x, pt.y);
  ctx.stroke();

  lastX = pt.x;
  lastY = pt.y;
}

function onPointerUp(e) {
  if (!isDrawing) return;
  isDrawing = false;
  saveGraffiti();
}

// ── API 交互 ──
async function loadGraffiti() {
  const response = await fetch(API_URL);
  if (!response.ok) return;
  const data = await response.json();

  if (data.image) {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const img = new Image();
    img.onload = () => {
      const context = canvas.getContext("2d");
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      context.clearRect(0, 0, w, h);
      context.drawImage(img, 0, 0, w, h);
      savingStatus.value = "加载完成";
    };
    img.src = data.image;
  } else {
    savingStatus.value = "空白画布，开始涂鸦吧";
  }
}

function saveGraffiti() {
  savingStatus.value = "保存中...";
  const canvas = canvasRef.value;
  if (!canvas) return;

  const dataUrl = canvas.toDataURL("image/png");

  fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: dataUrl }),
  })
    .then((res) => res.json())
    .then((data) => {
      savingStatus.value = data.status === "saved" ? "已保存" : "已更新";
      setTimeout(() => {
        if (savingStatus.value === "已保存" || savingStatus.value === "已更新") {
          savingStatus.value = "准备就绪";
        }
      }, 1500);
    })
    .catch((err) => {
      console.error("保存涂鸦失败:", err);
      savingStatus.value = "保存失败";
    });
}

// ── 生命周期 ──
onMounted(async () => {
  await nextTick();
  resizeCanvas();
  await loadGraffiti();

  resizeObserver = new ResizeObserver(() => {
    resizeCanvas();
  });
  resizeObserver.observe(canvasRef.value);
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
.canvas-wrapper {
  touch-action: none;
}

.graffiti-wall input[type="color"]::-webkit-color-swatch-wrapper {
  padding: 0;
}
.graffiti-wall input[type="color"]::-webkit-color-swatch {
  border: none;
  border-radius: 50%;
}
</style>
