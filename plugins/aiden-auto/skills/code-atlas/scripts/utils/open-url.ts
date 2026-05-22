import open from 'open'

export async function openUrl(url: string): Promise<void> {
  try {
    await open(url)
  } catch {
    // noop — caller can print URL manually
  }
}
