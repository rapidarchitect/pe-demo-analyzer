<script lang="ts">
  import { onMount } from 'svelte';
  import Dropzone from '$lib/Dropzone.svelte';
  import AnalysisProgress from '$lib/AnalysisProgress.svelte';
  import VitalsCard from '$lib/VitalsCard.svelte';
  import ClassificationBadge from '$lib/ClassificationBadge.svelte';
  import MetricsTable from '$lib/MetricsTable.svelte';
  import type { DealAnalysis } from '$lib/types';

  type AppState = 'idle' | 'analyzing' | 'results' | 'error';

  let state: AppState = 'idle';
  let currentStep = '';
  let selectedFiles: File[] = [];
  let result: DealAnalysis | null = null;
  let errorMessage = '';
  let showSettings = false;

  // LLM settings — persisted to localStorage
  let provider = 'anthropic';
  let llmModel = '';
  let llmApiKey = '';
  let llmBaseUrl = '';

  const STORAGE_KEY = 'pe_analyzer_settings';

  // Derived: Ollama needs a base URL; surface a hint if it's missing.
  $: ollamaBaseUrlMissing = provider === 'ollama' && !llmBaseUrl.trim();

  onMount(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const s = JSON.parse(saved);
        provider = s.provider ?? 'anthropic';
        llmModel = s.llmModel ?? '';
        llmApiKey = s.llmApiKey ?? '';
        llmBaseUrl = s.llmBaseUrl ?? '';
      }
    } catch {
      // ignore parse errors
    }
  });

  function onProviderChange() {
    // Auto-fill sensible defaults when switching provider type.
    if (provider === 'ollama') {
      if (!llmBaseUrl.trim()) llmBaseUrl = 'http://localhost:11434/v1';
      llmApiKey = ''; // Ollama doesn't use an API key
    } else if (provider === 'anthropic') {
      llmBaseUrl = '';
    }
  }

  function saveSettings() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ provider, llmModel, llmApiKey, llmBaseUrl }));
  }

  function onFiles(e: CustomEvent<File[]>) {
    selectedFiles = e.detail;
  }

  async function analyze() {
    if (!selectedFiles.length) return;
    state = 'analyzing';
    currentStep = 'extracting';
    result = null;
    errorMessage = '';

    saveSettings();

    const formData = new FormData();
    for (const file of selectedFiles) {
      formData.append('files', file);
    }

    // Pass LLM config overrides — backend ignores empty strings
    formData.append('provider', provider);
    if (llmModel.trim()) formData.append('llm_model', llmModel.trim());
    if (llmApiKey.trim()) formData.append('llm_api_key', llmApiKey.trim());
    if (llmBaseUrl.trim()) formData.append('llm_base_url', llmBaseUrl.trim());

    try {
      const response = await fetch('/analyze', { method: 'POST', body: formData });

      if (!response.ok || !response.body) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const event = JSON.parse(line.slice(6));

          if (event.type === 'progress') {
            currentStep = event.step;
          } else if (event.type === 'result') {
            result = event.data as DealAnalysis;
            state = 'results';
          } else if (event.type === 'error') {
            throw new Error(event.message);
          }
        }
      }
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : String(err);
      state = 'error';
    }
  }

  function reset() {
    state = 'idle';
    selectedFiles = [];
    result = null;
    errorMessage = '';
    currentStep = '';
  }

  function copyJson() {
    if (result) navigator.clipboard.writeText(JSON.stringify(result, null, 2));
  }
</script>

<svelte:head>
  <title>PE Deal Analyzer</title>
</svelte:head>

<div class="min-h-screen bg-zinc-50">
  <header class="border-b bg-white px-6 py-4">
    <div class="max-w-3xl mx-auto flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-zinc-900">PE Deal Analyzer</h1>
        <p class="text-xs text-zinc-400">Private Equity Deal Sourcing Assistant</p>
      </div>
      <button
        on:click={() => (showSettings = !showSettings)}
        title="LLM Settings"
        class="rounded-lg border px-3 py-2 text-xs font-medium text-zinc-500 hover:bg-zinc-50 transition-colors
               {showSettings ? 'bg-zinc-100 border-zinc-300' : 'border-zinc-200'}"
      >
        ⚙ Settings
      </button>
    </div>
  </header>

  {#if showSettings}
    <div class="border-b bg-white px-6 py-5">
      <div class="max-w-3xl mx-auto space-y-4">
        <p class="text-xs font-semibold uppercase tracking-wide text-zinc-400">LLM Configuration</p>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div class="space-y-1">
            <label class="block text-xs font-medium text-zinc-600" for="provider">Provider</label>
            <select
              id="provider"
              bind:value={provider}
              on:change={onProviderChange}
              class="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400"
            >
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="ollama">Ollama (local)</option>
              <option value="openai-compatible">OpenAI / Azure / Compatible</option>
            </select>
          </div>

          <div class="space-y-1">
            <label class="block text-xs font-medium text-zinc-600" for="llm-model">
              Model
              <span class="text-zinc-400 font-normal">(leave blank to use server default)</span>
            </label>
            <input
              id="llm-model"
              type="text"
              bind:value={llmModel}
              placeholder={provider === 'anthropic'
                ? 'claude-sonnet-4-6'
                : provider === 'ollama'
                ? 'qwen3.5:latest'
                : 'gpt-4o'}
              class="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-400"
            />
          </div>

          {#if provider === 'ollama' || provider === 'openai-compatible'}
            <div class="space-y-1">
              <label class="block text-xs font-medium text-zinc-600" for="llm-base-url">
                Base URL
                {#if provider === 'ollama'}
                  <span class="text-zinc-400 font-normal">(Ollama endpoint)</span>
                {:else}
                  <span class="text-zinc-400 font-normal">(full endpoint URL is fine)</span>
                {/if}
              </label>
              <input
                id="llm-base-url"
                type="text"
                bind:value={llmBaseUrl}
                placeholder={provider === 'ollama'
                  ? 'http://localhost:11434/v1'
                  : 'https://my-resource.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview'}
                class="w-full rounded-md border px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-400
                       {ollamaBaseUrlMissing ? 'border-amber-400 bg-amber-50' : 'border-zinc-300'}"
              />
              {#if ollamaBaseUrlMissing}
                <p class="text-xs text-amber-600">Set the Ollama endpoint URL to connect to your local instance.</p>
              {/if}
            </div>
          {/if}

          {#if provider !== 'ollama'}
            <div class="space-y-1">
              <label class="block text-xs font-medium text-zinc-600" for="llm-api-key-2">API Key</label>
              <input
                id="llm-api-key-2"
                type="password"
                bind:value={llmApiKey}
                placeholder="sk-..."
                autocomplete="off"
                class="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-400"
              />
            </div>
          {/if}
        </div>

        <!-- Summary chip — lets users confirm at a glance what's being sent -->
        <div class="flex items-center gap-2 rounded-md bg-zinc-50 border px-3 py-2 text-xs text-zinc-500 font-mono">
          <span class="font-semibold text-zinc-600">Will use:</span>
          <span class="text-zinc-800">{provider}</span>
          {#if llmModel.trim()}
            <span>·</span><span class="text-zinc-800">{llmModel.trim()}</span>
          {/if}
          {#if llmBaseUrl.trim()}
            <span>·</span><span class="truncate max-w-xs text-zinc-600">{llmBaseUrl.trim()}</span>
          {/if}
          {#if !llmModel.trim() && !llmBaseUrl.trim()}
            <span class="text-zinc-400">(server .env defaults)</span>
          {/if}
        </div>
        <p class="text-xs text-zinc-400">
          Settings are saved to local storage. Leave fields blank to use server-side environment variables.
        </p>
      </div>
    </div>
  {/if}

  <main class="max-w-3xl mx-auto px-6 py-10 space-y-6">

    {#if state === 'idle'}
      <Dropzone on:files={onFiles} />

      {#if selectedFiles.length > 0}
        <div class="rounded-lg bg-white border p-4 text-sm text-zinc-600">
          <p class="font-medium text-zinc-800 mb-2">{selectedFiles.length} file(s) selected:</p>
          <ul class="list-disc list-inside space-y-1">
            {#each selectedFiles as f}
              <li>{f.name}</li>
            {/each}
          </ul>
        </div>
      {/if}

      <button
        on:click={analyze}
        disabled={!selectedFiles.length}
        class="w-full rounded-lg bg-zinc-900 py-3 text-sm font-semibold text-white
               hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Analyze Deal
      </button>
    {/if}

    {#if state === 'analyzing'}
      <div class="rounded-xl border bg-white p-8 shadow-sm">
        <h2 class="font-semibold text-zinc-800 mb-6">Analyzing deal documents...</h2>
        <AnalysisProgress {currentStep} />
      </div>
    {/if}

    {#if state === 'results' && result}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <VitalsCard vitals={result.vitals} />
        <ClassificationBadge classification={result.classification} />
      </div>
      <MetricsTable metrics={result.metrics} category={result.classification.category} />

      <div class="flex gap-3">
        <button
          on:click={copyJson}
          class="rounded-lg border px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 transition-colors"
        >
          Copy JSON
        </button>
        <button
          on:click={reset}
          class="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white hover:bg-zinc-700 transition-colors"
        >
          Analyze Another Deal
        </button>
      </div>
    {/if}

    {#if state === 'error'}
      <div class="rounded-xl border border-red-200 bg-red-50 p-6">
        <p class="font-semibold text-red-700 mb-1">Analysis failed</p>
        <p class="text-sm text-red-600 font-mono break-all">{errorMessage}</p>
      </div>
      <button
        on:click={reset}
        class="rounded-lg border px-4 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100"
      >
        Try Again
      </button>
    {/if}

  </main>
</div>
