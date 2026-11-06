import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {LoginView} from '../components/LoginView';
import {tabsAllowedToRole} from '../services/roleScope';

const file=(path:string)=>readFileSync(path,'utf8');
const icon=file('public/icon.svg');
assert.match(icon,/viewBox="0 0 512 512"/);
assert.match(icon,/FR Finance/);
assert.match(icon,/#[0-9a-f]{6}/i);
assert.match(icon,/leaf|folhas/i);
const login=renderToStaticMarkup(
  React.createElement(LoginView,{onLoginSuccess:()=>undefined})
);
assert.match(login,/src="\/icon.svg"/);
assert.match(login,/Entrar na sua conta/);
assert.match(login,/Primeiro acesso/);
assert.match(login,/FR Finance/);
assert.match(login,/build/);
const loginSource=file('src/components/LoginView.tsx');
assert.match(loginSource,/Sou novo membro/);
assert.match(loginSource,/Quero administrar uma caixinha/);
assert.match(loginSource,/authService.login\(email.trim\(\), password, selectedRole\)/);
assert.doesNotMatch(loginSource,/authService\.register\(/);

const dashboard=file('src/components/DashboardView.tsx');
assert.match(dashboard,/fetchMasterOverview\(/);
assert.match(dashboard,/fetchTenantOverview\(/);
assert.match(dashboard,/POSTGRESQL_RLS/);
assert.match(dashboard,/tenant.role !== role/);
assert.match(dashboard,/tenant.tenant_id !== state.currentTenantId/);
assert.match(dashboard,/role === 'TENANT_ADMIN'/);
assert.doesNotMatch(dashboard,/R\$\s*1\.850/);
assert.doesNotMatch(dashboard,/setTimeout\(|Math.random\(/);
assert.deepEqual(tabsAllowedToRole('TENANT_MEMBER'),
  ['MEU_PAINEL','MINHAS_CONTRIBUICOES','MEU_EMPRESTIMO','MEU_RESULTADO','NOTIFICACOES']);

const app=file('src/App.tsx');
assert.doesNotMatch(app,/handleContextSwitch|profilePickerOpen|Trocar perfil/);
assert.match(app,/Administrador Master — Plataforma/);
assert.match(app,/isRoleTabAllowed\(state.currentRole, activeTab\)/);
assert.match(app,/navItems.slice\(0,3\)/);
assert.match(app,/Mais opções/);
const native=file('android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml');
assert.match(native,/@drawable\/ic_fr_foreground/);
assert.match(file('android/app/src/main/res/values/strings.xml'),/>FR Finance</);
assert.match(file('android/app/src/main/res/values/styles.xml'),/@drawable\/fr_launch/);
const manifest=JSON.parse(file('public/manifest.webmanifest'));
assert.equal(manifest.short_name,'FR Finance');
console.log('PREMIUM_BRAND_AND_ROLE_UI=PASS');
