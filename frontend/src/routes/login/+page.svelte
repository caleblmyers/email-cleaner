<script lang="ts">
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';

	const error = page.url.searchParams.get('error');
</script>

<div class="min-h-screen flex items-center justify-center bg-background p-4">
	<Card.Root class="w-full max-w-md">
		<Card.Header class="text-center">
			<div class="text-5xl mb-2">&#9993;</div>
			<Card.Title class="text-2xl">Email Cleaner</Card.Title>
			<Card.Description>Connect your Gmail to sort, categorize, and clean your inbox with AI.</Card.Description>
		</Card.Header>
		<Card.Content class="space-y-4">
			{#if error}
				<p class="text-sm text-destructive">Authentication error: {error}. Please try again.</p>
			{/if}
			<Button href="/auth/login" class="w-full" size="lg">Connect Gmail Account</Button>
		</Card.Content>
		<Card.Footer class="flex-col text-sm text-muted-foreground">
			<details class="w-full">
				<summary class="cursor-pointer hover:text-foreground transition-colors">What permissions are needed?</summary>
				<ul class="mt-2 ml-4 list-disc space-y-1">
					<li>Read and list your emails</li>
					<li>Move and archive emails</li>
					<li>Delete emails (to trash)</li>
					<li>Manage labels and folders</li>
				</ul>
				<p class="mt-2 text-xs">Your emails are processed locally. Only subject lines, sender names, and snippets are sent to Claude AI.</p>
			</details>
		</Card.Footer>
	</Card.Root>
</div>
