import React from 'react';
import Sidebar from './js/Sidebar';
import Chat from './js/Chat';
import RightSidebar from './js/RightSidebar';
import './css/style.css';

export default function App() {
  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', background: '#181c24' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Chat />
      </div>
      <RightSidebar />
    </div>
  );
}
