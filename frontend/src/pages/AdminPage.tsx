import './AdminPage.css';

export default function AdminPage() {
  return (
    <div className="admin-page">
      <div className="page-header">
        <h1>Administración</h1>
        <p className="page-subtitle">Gestión de la clínica</p>
      </div>

      <div className="admin-nav">
        <nav className="admin-tabs" role="tablist">
          <button role="tab" aria-selected="true" className="admin-tab active">
            Aranceles
          </button>
          <button role="tab" aria-selected="false" className="admin-tab">
            Odontólogos
          </button>
          <button role="tab" aria-selected="false" className="admin-tab">
            Sillones
          </button>
          <button role="tab" aria-selected="false" className="admin-tab">
            Configuración
          </button>
        </nav>
      </div>

      <div className="admin-content">
        <section className="admin-section" aria-labelledby="aranceles-heading">
          <div className="section-header">
            <h2 id="aranceles-heading">Aranceles</h2>
            <button className="btn btn-primary">Nuevo arancel</button>
          </div>
          <div className="table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Práctica</th>
                  <th>Duración</th>
                  <th>Precio</th>
                  <th>Seña %</th>
                  <th>Activo</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>LIM001</td>
                  <td>Limpieza dental</td>
                  <td>30 min</td>
                  <td>$15.000</td>
                  <td>30%</td>
                  <td><span className="badge active">Sí</span></td>
                  <td><button className="btn btn-sm btn-secondary">Editar</button></td>
                </tr>
                <tr>
                  <td>CAR001</td>
                  <td>Tratamiento de caries</td>
                  <td>45 min</td>
                  <td>$25.000</td>
                  <td>40%</td>
                  <td><span className="badge active">Sí</span></td>
                  <td><button className="btn btn-sm btn-secondary">Editar</button></td>
                </tr>
                <tr>
                  <td>EXT001</td>
                  <td>Extracción simple</td>
                  <td>30 min</td>
                  <td>$20.000</td>
                  <td>30%</td>
                  <td><span className="badge active">Sí</span></td>
                  <td><button className="btn btn-sm btn-secondary">Editar</button></td>
                </tr>
                <tr>
                  <td>ORT001</td>
                  <td>Control ortodoncia</td>
                  <td>20 min</td>
                  <td>$12.000</td>
                  <td>20%</td>
                  <td><span className="badge inactive">No</span></td>
                  <td><button className="btn btn-sm btn-secondary">Editar</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}