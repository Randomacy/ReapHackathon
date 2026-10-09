export default function Pending() {
  return <main className="plain">
    <div className="focus">
      <p className="brew-status">Brewing…</p>
      <div className="bar" role="progressbar" aria-label="Order confirmed"><div className="bar-fill" /></div>
      <p className="subtle">Close the tab to get back to focus</p>
    </div>
  </main>;
}
