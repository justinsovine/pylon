from pathlib import Path

import pytest


@pytest.fixture
def fake_php_repo(tmp_path: Path) -> Path:
    app_dir = tmp_path / "app" / "Models"
    app_dir.mkdir(parents=True)

    (app_dir / "User.php").write_text("""<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Model;

class User extends Model
{
    protected $table = 'users';

    protected $fillable = [
        'name',
        'email',
        'password',
    ];

    protected $casts = [
        'email_verified_at' => 'datetime',
    ];

    public function profiles()
    {
        return $this->hasMany(WorkerProfile::class);
    }

    public function client()
    {
        return $this->belongsTo(Client::class);
    }
}
""")

    (app_dir / "WorkerProfile.php").write_text("""<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Model;

class WorkerProfile extends Model
{
    protected $fillable = ['user_id', 'first_name', 'last_name', 'status'];

    public function user()
    {
        return $this->belongsTo(User::class);
    }
}
""")

    controllers_dir = tmp_path / "app" / "Http" / "Controllers"
    controllers_dir.mkdir(parents=True)

    (controllers_dir / "UserController.php").write_text("""<?php

namespace App\\Http\\Controllers;

class UserController extends Controller
{
    public function index() {}
    public function show($id) {}
    public function store() {}
    public function update($id) {}
    public function destroy($id) {}
}
""")

    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()

    (routes_dir / "web.php").write_text("""<?php
Route::get('/users', [UserController::class, 'index']);
Route::post('/users', [UserController::class, 'store']);
Route::get('/users/{id}', [UserController::class, 'show']);
Route::put('/users/{id}', [UserController::class, 'update']);
Route::delete('/users/{id}', [UserController::class, 'destroy']);
""")

    return tmp_path


def test_tree_sitter_extract_classes(fake_php_repo: Path):
    from src.pylon.harness.analyzers.tree_sitter_php import extract_classes

    classes = extract_classes(str(fake_php_repo))
    names = {c.name for c in classes}
    assert "User" in names
    assert "WorkerProfile" in names
    assert "UserController" in names


def test_tree_sitter_extract_models(fake_php_repo: Path):
    from src.pylon.harness.analyzers.tree_sitter_php import extract_models

    models = extract_models(str(fake_php_repo))
    names = {m.name for m in models}
    assert "User" in names
    assert "WorkerProfile" in names

    user = next(m for m in models if m.name == "User")
    assert user.table == "users"
    assert "name" in user.fillable
    assert "email" in user.fillable
    assert any("hasMany" in r for r in user.relationships)
    assert any("belongsTo" in r for r in user.relationships)


def test_tree_sitter_format_models(fake_php_repo: Path):
    from src.pylon.harness.analyzers.tree_sitter_php import extract_models, format_models

    models = extract_models(str(fake_php_repo))
    output = format_models(models)
    assert "# Models" in output
    assert "User" in output
    assert "`users`" in output


def test_route_extraction_static(fake_php_repo: Path):
    import asyncio

    from src.pylon.harness.analyzers.php_routes import _extract_routes_static

    routes = asyncio.run(_extract_routes_static(str(fake_php_repo)))
    assert len(routes) >= 4
    methods = {r.method for r in routes}
    assert "GET" in methods
    assert "POST" in methods


def test_check_tools():
    from src.pylon.harness.preinvestigate import check_tools

    tools = check_tools()
    assert isinstance(tools, dict)
    assert "rg" in tools
    assert "ctags" in tools


@pytest.mark.asyncio
async def test_pre_investigation_runs(fake_php_repo: Path, tmp_path: Path):
    from src.pylon.harness.preinvestigate import run_pre_investigation

    notes_path = tmp_path / "notes" / "test-ticket"
    notes_path.mkdir(parents=True)

    sections = await run_pre_investigation(
        repo_path=str(fake_php_repo),
        notes_path=str(notes_path),
        keywords=["User", "profile"],
        skip_phpstan=True,
    )

    assert "classes.md" in sections
    assert "models.md" in sections
    assert "routes.md" in sections
    assert "summary.md" in sections

    preinvest_dir = notes_path / ".pylon" / "pre-investigation"
    assert preinvest_dir.exists()
    assert (preinvest_dir / "summary.md").exists()
