export const DraggableNode = ({ type, label }) => {
  const onDragStart = (event, nodeType) => {
    const appData = { nodeType };

    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify(appData)
    );

    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      className={type}
      onDragStart={(event) => onDragStart(event, type)}
      draggable
      style={{
        cursor: 'grab',
        minWidth: '100px',
        height: '55px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',

        background: '#222222',
        color: '#ffffff',

        border: '1px solid #d1d5db',
        borderRadius: '12px',

        fontWeight: 600,
        fontSize: '15px',

        boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
      }}
    >
      {label}
    </div>
  );
};