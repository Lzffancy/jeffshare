<template>
  <!-- ── 导航 tabs ── -->
  <div class="tabs tabs-lifted mb-4" v-if="tab === 'summarize' || tab === 'upload'">
    <a
      class="tab tab-sm"
      :class="{ 'tab-active': tab === 'summarize' }"
      @click="tab = 'summarize'"
    >AI 会话沉淀</a>
    <a
      class="tab tab-sm"
      :class="{ 'tab-active': tab === 'upload' }"
      @click="tab = 'upload'"
    >文件上传发布</a>
  </div>

  <!-- ═══════════════════ AI 会话沉淀 ═══════════════════ -->
  <template v-if="tab === 'summarize'">
    <!-- ── idle: 粘贴对话 ── -->
    <div v-if="phase === 'idle' || phase === 'error'" class="card bg-base-100 shadow-md">
      <div class="card-body">
        <h2 class="card-title text-primary text-lg">AI 会话沉淀</h2>
        <p class="text-sm text-base-content/60">粘贴你与 AI 的对话内容，自动生成结构化博客草稿</p>

        <textarea
          v-model="conversation"
          class="textarea textarea-bordered w-full h-48 mt-3 font-mono text-sm"
          placeholder="在此粘贴 AI 对话内容..."
          :disabled="phase === 'loading'"
        ></textarea>

        <div v-if="phase === 'error'" role="alert" class="alert alert-error mt-2">
          <span>{{ errorMsg }}</span>
        </div>

        <div class="card-actions justify-end mt-3">
          <button
            class="btn btn-primary"
            :disabled="!conversation.trim() || phase === 'loading'"
            @click="doSummarize"
          >
            <span v-if="phase === 'loading'" class="loading loading-spinner loading-sm"></span>
            {{ phase === 'loading' ? '正在分析...' : '生成总结 →' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── editing: 预览 & 编辑 ── -->
    <div v-if="phase === 'editing' || phase === 'saving'" class="space-y-4">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- 左侧编辑区 -->
        <div class="card bg-base-100 shadow-md">
          <div class="card-body p-4">
            <h3 class="text-sm font-bold text-primary mb-2">Markdown 编辑</h3>
            <textarea
              v-model="markdown"
              class="textarea textarea-bordered w-full font-mono text-sm leading-relaxed"
              style="min-height: 60vh"
            ></textarea>
          </div>
        </div>

        <!-- 右侧预览 -->
        <div class="card bg-base-100 shadow-md">
          <div class="card-body p-4 overflow-auto" style="max-height: 75vh">
            <h3 class="text-sm font-bold text-primary mb-2">实时预览</h3>
            <div class="preview-content" v-html="renderedHTML"></div>
          </div>
        </div>
      </div>

      <div class="card bg-base-100 shadow-md">
        <div class="card-body">
          <div class="flex flex-wrap items-center gap-3">
            <div class="flex-1 text-sm">
              <span class="font-semibold">标题：</span>{{ result.title }}
              <span class="mx-2 text-base-content/30">|</span>
              <span class="font-semibold">Slug：</span><code>{{ result.slug }}</code>
            </div>
            <div class="flex flex-wrap gap-1">
              <span v-for="t in result.tags" class="badge badge-sm bg-[#e8f4fd] text-[#0277bd] border-0">{{ t }}</span>
            </div>
          </div>

          <div v-if="phase === 'saving'" class="mt-3">
            <span class="loading loading-spinner loading-sm"></span>
            <span class="ml-2 text-sm text-base-content/60">正在保存...</span>
          </div>

          <div class="card-actions justify-end mt-3">
            <button class="btn btn-outline btn-sm" @click="reset" :disabled="phase === 'saving'">重新开始</button>
            <button class="btn btn-primary" @click="doSave" :disabled="phase === 'saving'">保存草稿 →</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── saved: 完成 ── -->
    <div v-if="phase === 'saved'" class="card bg-base-100 shadow-md">
      <div class="card-body text-center py-10">
        <div class="text-4xl mb-4">✅</div>
        <h2 class="card-title justify-center text-success">保存成功</h2>
        <p class="text-sm text-base-content/60 mt-2">
          已保存到 <code class="bg-base-200 px-1 rounded">{{ savePath }}</code>
        </p>
        <p class="text-xs text-base-content/40 mt-1">
          <code>git commit && git push origin main</code> 后自动部署上线
        </p>
        <div class="card-actions justify-center mt-4">
          <a :href="`/blog/${result.slug}`" class="btn btn-outline btn-sm">查看文章</a>
          <button class="btn btn-primary btn-sm" @click="reset">再写一篇</button>
        </div>
      </div>
    </div>
  </template>

  <!-- ═══════════════════ 文件上传发布 ═══════════════════ -->
  <template v-if="tab === 'upload'">
    <!-- ── 未登录 ── -->
    <div v-if="authChecked && !authed" class="card bg-base-100 shadow-md">
      <div class="card-body text-center py-10">
        <div class="text-4xl mb-4">🔐</div>
        <h2 class="card-title justify-center text-primary">需要登录</h2>
        <p class="text-sm text-base-content/60 mt-2">
          文件上传仅限站长使用，请通过 GitHub OAuth 验证身份
        </p>
        <div class="card-actions justify-center mt-4">
          <a :href="`/admin-auth?redirect=/workbench/`" class="btn btn-primary">
            <svg class="w-4 h-4 mr-1" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
            Login with GitHub
          </a>
        </div>
        <p class="text-xs text-base-content/40 mt-3">
          登录后可上传 .md / .html 及其图片资源，自动发布
        </p>
      </div>
    </div>

    <!-- ── 鉴权检查中 ── -->
    <div v-if="!authChecked" class="card bg-base-100 shadow-md">
      <div class="card-body text-center py-10">
        <span class="loading loading-spinner loading-md"></span>
        <p class="text-sm text-base-content/60 mt-2">正在验证身份...</p>
      </div>
    </div>

    <!-- ── 已登录: 上传区域 ── -->
    <div v-if="authed" class="card bg-base-100 shadow-md">
      <div class="card-body">
        <div class="flex items-center justify-between mb-2">
          <h2 class="card-title text-primary text-lg">文件上传发布</h2>
          <span class="text-xs text-base-content/50">{{ userLogin }} · <button class="link link-hover text-xs" @click="doLogout">退出</button></span>
        </div>
        <p class="text-sm text-base-content/60">
          上传 .md / .html 及其图片附件，Claude 自动处理后发布到博客
        </p>

        <!-- 拖拽上传区 -->
        <div
          class="border-2 border-dashed rounded-lg p-8 text-center mt-3 transition-colors"
          :class="dragOver ? 'border-primary bg-primary/5' : 'border-base-300'"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <div v-if="!selectedFiles.length" class="space-y-2">
            <div class="text-3xl">📁</div>
            <p class="text-sm text-base-content/60">拖拽文件到此处，或点击选择</p>
            <label class="btn btn-outline btn-sm">
              选择文件
              <input type="file" multiple class="hidden" @change="onFileSelect" />
            </label>
          </div>
          <div v-else class="space-y-2">
            <div class="text-2xl">📋</div>
            <div class="text-sm">
              <span v-for="(f, i) in selectedFiles" :key="i" class="badge badge-sm mr-1 mb-1">{{ f.name }}</span>
            </div>
            <p class="text-xs text-base-content/40">{{ selectedFiles.length }} 个文件</p>
            <div class="flex gap-2 justify-center">
              <button class="btn btn-primary btn-sm" @click="doUpload" :disabled="uploading">
                <span v-if="uploading" class="loading loading-spinner loading-xs"></span>
                {{ uploading ? '处理中...' : '上传并发布 →' }}
              </button>
              <button class="btn btn-outline btn-sm" @click="clearFiles" :disabled="uploading">清除</button>
            </div>
          </div>
        </div>

        <!-- 上传结果 -->
        <div v-if="uploadResult" role="alert" :class="uploadResult.success ? 'alert alert-success mt-3' : 'alert alert-error mt-3'">
          <span>{{ uploadResult.message }}</span>
          <div v-if="uploadResult.detail" class="mt-2">
            <pre class="text-xs whitespace-pre-wrap max-h-32 overflow-auto">{{ uploadResult.detail }}</pre>
          </div>
        </div>
      </div>
    </div>
  </template>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";

// ── tab ──
const tab = ref("summarize"); // summarize | upload

// ── auth ──
const authChecked = ref(false);
const authed = ref(false);
const userLogin = ref("");

onMounted(async () => {
  tab.value = window.location.hash === "#upload" ? "upload" : "summarize";
  try {
    const resp = await fetch("/admin-auth/verify", { credentials: "include" });
    if (resp.ok) {
      const data = await resp.json();
      authed.value = true;
      userLogin.value = data.login || "";
    }
  } catch {
    // 未登录或网络异常，保持 unauthenticated
  } finally {
    authChecked.value = true;
  }
});

function doLogout() {
  document.cookie = "jeff_sid=; max-age=0; path=/";
  authed.value = false;
  userLogin.value = "";
}

// ── upload state ──
const selectedFiles = ref([]);
const dragOver = ref(false);
const uploading = ref(false);
const uploadResult = ref(null);

function onDrop(e) {
  dragOver.value = false;
  selectedFiles.value = Array.from(e.dataTransfer.files);
  uploadResult.value = null;
}

function onFileSelect(e) {
  selectedFiles.value = Array.from(e.target.files);
  uploadResult.value = null;
}

function clearFiles() {
  selectedFiles.value = [];
  uploadResult.value = null;
}

async function doUpload() {
  if (!selectedFiles.value.length) return;
  uploading.value = true;
  uploadResult.value = null;
  try {
    const form = new FormData();
    for (const f of selectedFiles.value) {
      form.append("files", f);
    }
    const resp = await fetch("/api/upload", {
      method: "POST",
      body: form,
      credentials: "include",
    });
    const data = await resp.json();
    uploadResult.value = data;
    if (data.success) {
      selectedFiles.value = [];
    }
  } catch {
    uploadResult.value = { success: false, message: "网络错误，上传失败" };
  } finally {
    uploading.value = false;
  }
}

// ── summarize state ──
const phase = ref("idle"); // idle | loading | editing | saving | saved | error
const conversation = ref("");
const result = ref({ title: "", slug: "", tags: [], markdown: "", summary: "" });
const markdown = ref("");
const savePath = ref("");
const errorMsg = ref("");

// ── 简易 Markdown → HTML ──
function simpleRender(md) {
  let html = md;
  // code blocks (fenced)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<pre><code>${escaped}</code></pre>`;
  });
  // inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // headings
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // bold & italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // images
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
  // blockquotes
  html = html.replace(/^> (.+)$/gm, "<blockquote>$1</blockquote>");
  // horizontal rules
  html = html.replace(/^---$/gm, "<hr>");
  // unordered lists
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");
  // ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
  // paragraphs (double newlines)
  const blocks = html.split(/\n\n+/);
  html = blocks.map((block) => {
    block = block.trim();
    if (!block) return "";
    if (/^<(h[1-6]|ul|ol|pre|blockquote|hr|table)/.test(block)) return block;
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    return `<p>${lines.join("<br>")}</p>`;
  }).join("\n");
  return html;
}

const renderedHTML = computed(() => simpleRender(markdown.value));

// ── actions ──
async function doSummarize() {
  phase.value = "loading";
  errorMsg.value = "";
  try {
    const resp = await fetch("/api/agent/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation: conversation.value }),
    });
    const data = await resp.json();
    if (!data.success) {
      errorMsg.value = data.detail || "总结失败";
      phase.value = "error";
      return;
    }
    result.value = data.result;
    markdown.value = data.result.markdown;
    phase.value = "editing";
  } catch (e) {
    errorMsg.value = "网络错误，请检查后端是否运行";
    phase.value = "error";
  }
}

async function doSave() {
  phase.value = "saving";
  try {
    const resp = await fetch("/api/agent/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug: result.value.slug, markdown: markdown.value }),
    });
    const data = await resp.json();
    if (!data.success) {
      errorMsg.value = data.detail || "保存失败";
      phase.value = "error";
      return;
    }
    savePath.value = data.path;
    phase.value = "saved";
  } catch (e) {
    errorMsg.value = "保存失败，请检查后端是否运行";
    phase.value = "error";
  }
}

function reset() {
  phase.value = "idle";
  conversation.value = "";
  result.value = { title: "", slug: "", tags: [], markdown: "", summary: "" };
  markdown.value = "";
  errorMsg.value = "";
  savePath.value = "";
}
</script>

<style scoped>
.preview-content :deep(h1) {
  color: var(--color-primary);
  font-size: 1.5rem;
  font-weight: 800;
  margin: 1rem 0 0.5rem;
}
.preview-content :deep(h2) {
  color: var(--color-primary);
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0.75rem 0 0.5rem;
}
.preview-content :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0.5rem 0 0.25rem;
}
.preview-content :deep(p) { margin: 0.5rem 0; }
.preview-content :deep(ul), .preview-content :deep(ol) {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}
.preview-content :deep(li) { margin: 0.25rem 0; }
.preview-content :deep(code) {
  background: #f0f0f0;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-size: 0.85em;
}
.preview-content :deep(pre) {
  background: #0b1e3d;
  color: #ecf0f1;
  padding: 0.75rem;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0.5rem 0;
}
.preview-content :deep(pre code) {
  background: none;
  padding: 0;
}
.preview-content :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  padding-left: 0.75rem;
  color: #666;
  margin: 0.5rem 0;
}
.preview-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-base-300);
  margin: 1rem 0;
}
.preview-content :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
}
.preview-content :deep(img) {
  max-width: 100%;
  border-radius: 0.5rem;
}
</style>
