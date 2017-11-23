package sibai1nk.cps496a.cmich.edu.chatbotcompanionapp;

import android.support.v7.app.AppCompatActivity;
import android.os.Bundle;
import android.support.v7.widget.LinearLayoutManager;
import android.support.v7.widget.RecyclerView;

import com.google.firebase.database.DataSnapshot;
import com.google.firebase.database.DatabaseError;
import com.google.firebase.database.DatabaseReference;
import com.google.firebase.database.FirebaseDatabase;
import com.google.firebase.database.Query;
import com.google.firebase.database.ValueEventListener;

import java.util.ArrayList;
import java.util.List;


public class MainActivity extends AppCompatActivity {

    private RecyclerView mRecyclerView;
    private RecyclerView.Adapter mAdapter;
    private RecyclerView.LayoutManager mLayoutManager;
    String[] myDataset = new String[25];
    List<String> where = new ArrayList<String>();
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        DatabaseReference databaseReference = FirebaseDatabase.getInstance().getReference();
        Query lastQuery = databaseReference.child("messages").orderByKey().limitToLast(25);
        lastQuery.addValueEventListener(new ValueEventListener() {
            @Override
            public void onDataChange(DataSnapshot dataSnapshot) {
                int count = 0;
                for (DataSnapshot snapshot : dataSnapshot.getChildren()) {
                    String cur = "";
                    try {
                        cur = snapshot.getValue().toString();
                        cur = cur.replace("-", "").replace("{", "").replace("}", "");
                        cur = cur.substring(28, cur.length());
                    } catch (Exception e) {
                    }
                    System.out.println(cur);
                    where.add(cur);

                }
                myDataset = new String[where.size()];
                where.toArray(myDataset);
            }
            @Override
            public void onCancelled(DatabaseError databaseError) {
            }
        });
        myDataset = new String[where.size()];
        System.out.println(where.size());
        where.toArray(myDataset);
        myDataset = new String[]{"Check", "Check1", "Check2"};
        for (String i : myDataset) {
            System.out.println(i);
        }
        mRecyclerView = (RecyclerView) findViewById(R.id.my_recycler_view);
        // use this setting to improve performance if you know that changes
        // in content do not change the layout size of the RecyclerView
        mRecyclerView.setHasFixedSize(true);

        // use a linear layout manager
        mLayoutManager = new LinearLayoutManager(this);
        mRecyclerView.setLayoutManager(mLayoutManager);

        // specify an adapter (see also next example)

        mAdapter = new MyAdapter(myDataset);
        mRecyclerView.setAdapter(mAdapter);
    }

}
