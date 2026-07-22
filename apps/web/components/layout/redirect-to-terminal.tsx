export function RedirectToTerminal({ target }: { target: string }) {
  return (
    <>
      <title>Redirecting to PCIndex</title>
      <meta httpEquiv="refresh" content={`0;url=${target}`} />
      <main>
        <a href={target}>Continue to the terminal</a>
      </main>
      <script
        dangerouslySetInnerHTML={{
          __html: `location.replace(${JSON.stringify(target)})`,
        }}
      />
    </>
  )
}
