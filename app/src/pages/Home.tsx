import NavBar from '../components/NavBar';
import Map from '../components/Map';

function Home() {
    return (
        <div className="home-container">
            <NavBar />
            {/* <HomeContent /> */}
            <Map />
            {/* <InfoSummary /> */}
            {/* <HomeFooter /> */}
        </div>
    );
}

export default Home;