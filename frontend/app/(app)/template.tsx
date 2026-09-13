/** Each signed-in screen fades in on navigation. Opacity only: the shell, sticky bars and dialogs stay put. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-route-in">{children}</div>;
}
