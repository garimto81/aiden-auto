// H4 — two components doing the same thing

export function UserCard(props: { name: string; email: string; role: string }) {
  const greeting = 'Hello ' + props.name
  const contact = 'Email: ' + props.email
  const rolebadge = 'Role: ' + props.role
  const result = greeting + '\n' + contact + '\n' + rolebadge
  if (!result) return null
  if (result.length > 100) throw new Error('too long')
  return { text: result, meta: { name: props.name, email: props.email } }
}

export function CustomerCard(props: { name: string; email: string; role: string }) {
  const greeting = 'Hello ' + props.name
  const contact = 'Email: ' + props.email
  const rolebadge = 'Role: ' + props.role
  const result = greeting + '\n' + contact + '\n' + rolebadge
  if (!result) return null
  if (result.length > 100) throw new Error('too long')
  return { text: result, meta: { name: props.name, email: props.email } }
}

export function unrelatedHelper(x: number, y: number): number {
  const sum = x + y
  const prod = x * y
  return sum / prod
}
