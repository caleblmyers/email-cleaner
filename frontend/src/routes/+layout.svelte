<script lang="ts">
	import '../app.css';
	import { Toaster } from 'svelte-sonner';
	import { loading } from '$lib/stores/loading.svelte';
	let { children } = $props();
</script>

{@render children()}

<Toaster richColors position="top-right" />

{#if loading.active}
	<div class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
		<div class="bg-card rounded-lg p-8 shadow-xl text-center">
			<div class="animate-spin h-8 w-8 border-4 border-muted border-t-primary rounded-full mx-auto mb-3"></div>
			<p class="text-sm text-muted-foreground">{loading.message}</p>
		</div>
	</div>
{/if}
