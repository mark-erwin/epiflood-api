function Credits() {
  const contributors = [
    'Nathan Seth De Guzman',
    'Mark Erwin Pesino',
    'Nathan Pabico',
    'Roy Kevin Navarro',
    'Yvan Luis Senen',
  ];

  return (
    <main className="flex min-h-[calc(100vh-5.5rem)] flex-col items-center justify-center bg-[#f4f6fb] px-6 py-12 font-['Montserrat',sans-serif]">
      <h1
        className="
          mb-8 p-5 text-center text-[clamp(2rem,4vw,3rem)] font-bold leading-[1.2]
          tracking-[-0.04em] text-[#080f43]
          after:mx-auto after:mt-[0.8rem] after:block after:h-1 after:w-16
          after:rounded-[2px] after:bg-[#3449a3] after:content-['']
        "
      >
        Contributors
      </h1>

      <ul className="m-0 flex w-full max-w-xl list-none flex-col gap-3 rounded-2xl border border-[#e1e6f0] bg-white p-6 text-center leading-normal shadow-[0_8px_30px_rgba(8,15,67,0.08)]">
        {contributors.map((name) => (
          <li
            key={name}
            className="
              flex items-center gap-4 rounded-[0.65rem] border border-transparent
              bg-[#f7f8fc] px-[1.1rem] py-4 text-base font-medium leading-normal text-[#1d2648]
              transition duration-200 ease-in-out
              before:h-[0.65rem] before:w-[0.65rem] before:shrink-0 before:rounded-full
              before:bg-[#3449a3] before:content-['']
              hover:translate-x-[5px] hover:border-[#d8defa] hover:bg-[#eef1ff]
              hover:shadow-[0_4px_12px_rgba(8,15,67,0.06)]
            "
          >
            {name}
          </li>
        ))}
      </ul>
    </main>
  );
}

export default Credits;