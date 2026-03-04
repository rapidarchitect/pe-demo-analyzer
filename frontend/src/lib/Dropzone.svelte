<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{ files: File[] }>();

  let dragging = false;

  const ACCEPTED = '.pdf,.docx,.xlsx,.pptx,.txt';

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length) dispatch('files', files);
  }

  function handleChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    if (files.length) dispatch('files', files);
  }
</script>

<!-- Using <label> instead of <button> + programmatic .click() avoids the macOS/Safari
     "greyed-out" file picker bug caused by opening the dialog from a programmatic event. -->
<label
  class="block w-full cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors
         {dragging ? 'border-blue-500 bg-blue-50' : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50'}"
  on:dragover|preventDefault={() => (dragging = true)}
  on:dragleave={() => (dragging = false)}
  on:drop={handleDrop}
>
  <input
    type="file"
    multiple
    accept={ACCEPTED}
    class="sr-only"
    on:change={handleChange}
  />
  <div class="pointer-events-none space-y-2">
    <p class="text-lg font-medium text-zinc-700">Drop files here or click to upload</p>
    <p class="text-sm text-zinc-400">PDF · DOCX · XLSX · PPTX · TXT · Multiple files supported</p>
  </div>
</label>
