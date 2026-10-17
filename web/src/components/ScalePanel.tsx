// Measured numbers, copied from docs/prediction-model.md, docs/scalability.md
// and artifacts/ui-scalability.json. Update them together when re-benchmarking.
const MODEL = [
  { step: 'Rent-pressure predictions', value: '9.5M / s', note: 'Every LA County tract re-scored in milliseconds' },
  { step: 'Tract model fit', value: '0.007 s', note: 'Logistic regression' },
  { step: 'Tract features, all LA County, 3 periods', value: '1.9 s', note: '' },
  { step: 'Business model fit', value: '2.1 s', note: '491k businesses' },
  { step: 'Business predictions', value: '745k / s', note: '1M rows in 1.3 s' },
  { step: 'Raw data download', value: '~5 min', note: 'One time, cached' },
];

const GROWTH = [
  { areas: '10', build: '0.45 ms', render: '—', json: '0.07 MB', cost: '$0.04' },
  { areas: '100', build: '4.62 ms', render: '78.7 ms', json: '0.66 MB', cost: '$0.40' },
  { areas: '1,000', build: '53.3 ms', render: '328.8 ms', json: '6.60 MB', cost: '$3.97' },
];

export function ScalePanel() {
  return (
    <section className="scale-panel" aria-labelledby="scale-title">
      <p className="historical-eyebrow">Measured on a laptop CPU · single process</p>
      <h2 id="scale-title">Compute is not the bottleneck.</h2>
      <p className="scale-lede">Scaling to all ~9,000 California tracts is a data-download task. Photo coverage, not compute, limits the image layer.</p>

      <div className="scale-stats">
        {MODEL.map(row => (
          <div key={row.step} className="scale-stat">
            <strong>{row.value}</strong>
            <span>{row.step}</span>
            {row.note && <small>{row.note}</small>}
          </div>
        ))}
      </div>

      <h3>From 10 to 1,000 areas</h3>
      <div className="scale-table-wrap">
        <table className="scale-table">
          <thead>
            <tr><th scope="col">Areas</th><th scope="col">Score + build</th><th scope="col">Browser render</th><th scope="col">Data size</th><th scope="col">Image API cost*</th></tr>
          </thead>
          <tbody>
            {GROWTH.map(row => (
              <tr key={row.areas}><th scope="row">{row.areas}</th><td>{row.build}</td><td>{row.render}</td><td>{row.json}</td><td>{row.cost}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="scale-note">Medians of repeated runs. Inputs are synthetic; the real 30-area Inglewood pilot renders in 61.5 ms. *Cost is projected from nine real GPT-4.1 mini calls at published prices, not a measured bill. Image download and human review time are not measured.</p>
    </section>
  );
}
